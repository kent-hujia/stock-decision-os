from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.stocks import _stock_or_404
from app.models.database import get_db
from app.models.schemas import Decision, DecisionStep, SkepticAnswer, SkepticReview, ThesisMonitor
from app.services import claude, skeptic, thesis_monitor

router = APIRouter()


class DecisionCreate(BaseModel):
    ticker: str = Field(..., max_length=10)
    thesis: str = Field(..., min_length=10, max_length=3000)
    conviction: int = Field(..., ge=1, le=10)


class DecisionUpdate(BaseModel):
    thesis: Optional[str] = Field(None, min_length=10, max_length=3000)
    conviction: Optional[int] = Field(None, ge=1, le=10)
    note: Optional[str] = Field(None, max_length=1000)


class RebuttalCreate(BaseModel):
    question_index: int = Field(..., ge=0, le=2)
    rebuttal: str = Field(..., min_length=1, max_length=2000)


class MonitorCreate(BaseModel):
    metric: thesis_monitor.MetricKey
    operator: thesis_monitor.Operator
    threshold: float
    rationale: Optional[str] = Field(None, max_length=500)


def _iso(dt) -> Optional[str]:
    dt = claude.as_utc(dt)
    return dt.isoformat() if dt else None


def _decision_or_404(db: Session, decision_id: int) -> Decision:
    decision = db.get(Decision, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="找不到這筆投資決策。")
    return decision


def _summary(d: Decision) -> Dict[str, Any]:
    review = d.reviews[-1] if d.reviews else None
    graded = _latest_answers(review) if review else {}
    return {
        "id": d.id, "ticker": d.ticker, "stock_name": d.stock_name, "thesis": d.thesis,
        "conviction": d.conviction, "created_at": _iso(d.created_at),
        "updated_at": _iso(d.updated_at or d.created_at),
        "monitor_count": len(d.monitors),
        "skeptic": None if review is None else {
            "status": review.status,
            "passed": sum(1 for a in graded.values() if a.verdict == "Pass"),
            "failed": sum(1 for a in graded.values() if a.verdict == "Fail"),
        },
    }


def _latest_answers(review: SkepticReview) -> Dict[int, SkepticAnswer]:
    latest: Dict[int, SkepticAnswer] = {}
    for a in review.answers:  # ordered by id, so later answers win
        latest[a.question_index] = a
    return latest


def _answer(a: SkepticAnswer) -> Dict[str, Any]:
    return {"id": a.id, "question_index": a.question_index, "rebuttal": a.rebuttal, "status": a.status,
            "verdict": a.verdict, "reason": a.reason, "error": a.error, "created_at": _iso(a.created_at)}


def _review(r: Optional[SkepticReview]) -> Optional[Dict[str, Any]]:
    if r is None:
        return None
    latest = _latest_answers(r)
    return {"id": r.id, "status": r.status, "error": r.error, "data_as_of": r.data_as_of,
            "created_at": _iso(r.created_at),
            "questions": [{**q, "index": i, "answer": _answer(latest[i]) if i in latest else None}
                          for i, q in enumerate(r.questions or [])]}


def _detail(d: Decision) -> Dict[str, Any]:
    return {
        **_summary(d),
        "monitor_status": d.monitor_status, "monitor_error": d.monitor_error,
        "monitors": [thesis_monitor.serialize_monitor(m) for m in d.monitors],
        "review": _review(d.reviews[-1] if d.reviews else None),
        "steps": [{"id": s.id, "step_type": s.step_type, "content": s.content, "created_at": _iso(s.created_at)}
                  for s in reversed(d.steps)],
    }


@router.get("")
def list_decisions(db: Session = Depends(get_db)):
    return [_summary(d) for d in db.query(Decision).order_by(Decision.id.desc()).all()]


@router.post("")
def create_decision(payload: DecisionCreate, db: Session = Depends(get_db)):
    stock = _stock_or_404(payload.ticker)
    thesis = payload.thesis.strip()
    decision = Decision(ticker=stock["stock_id"], stock_name=stock["name"],
                        thesis=thesis, conviction=payload.conviction)
    db.add(decision)
    db.flush()
    db.add(DecisionStep(decision_id=decision.id, step_type="created",
                        content={"thesis": thesis, "conviction": payload.conviction}))
    db.commit()
    thesis_monitor.start_extraction(db, decision)
    return _detail(decision)


@router.get("/{decision_id}")
def get_decision(decision_id: int, db: Session = Depends(get_db)):
    return _detail(_decision_or_404(db, decision_id))


@router.patch("/{decision_id}")
def update_decision(decision_id: int, payload: DecisionUpdate, db: Session = Depends(get_db)):
    decision = _decision_or_404(db, decision_id)
    note = (payload.note or "").strip() or None
    if payload.conviction is not None and payload.conviction != decision.conviction:
        db.add(DecisionStep(decision_id=decision.id, step_type="conviction_updated",
                            content={"from": decision.conviction, "to": payload.conviction, "note": note}))
        decision.conviction = payload.conviction
    thesis = (payload.thesis or "").strip()
    if thesis and thesis != decision.thesis:
        db.add(DecisionStep(decision_id=decision.id, step_type="thesis_updated",
                            content={"from": decision.thesis, "to": thesis, "note": note}))
        decision.thesis = thesis
    db.commit()
    db.refresh(decision)
    return _detail(decision)


@router.delete("/{decision_id}", status_code=204)
def delete_decision(decision_id: int, db: Session = Depends(get_db)):
    db.delete(_decision_or_404(db, decision_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{decision_id}/skeptic")
def start_skeptic(decision_id: int, regenerate: bool = False, db: Session = Depends(get_db)):
    decision = _decision_or_404(db, decision_id)
    skeptic.start_review(db, decision, regenerate)
    db.refresh(decision)
    return _detail(decision)


@router.post("/{decision_id}/skeptic/answers")
def answer_skeptic(decision_id: int, payload: RebuttalCreate, db: Session = Depends(get_db)):
    decision = _decision_or_404(db, decision_id)
    review = decision.reviews[-1] if decision.reviews else None
    if review is None or review.status != "done":
        raise HTTPException(status_code=409, detail="還沒有可以回答的質疑問題。")
    current = _latest_answers(review).get(payload.question_index)
    if current and current.status == "pending" and not claude.is_stale(current.created_at):
        raise HTTPException(status_code=409, detail="這一題的回答還在評分中，請稍候。")
    skeptic.submit_answer(db, review, payload.question_index, payload.rebuttal.strip())
    db.refresh(decision)
    return _detail(decision)


@router.post("/{decision_id}/monitors/extract")
def extract_monitors(decision_id: int, db: Session = Depends(get_db)):
    decision = _decision_or_404(db, decision_id)
    thesis_monitor.start_extraction(db, decision)
    return _detail(decision)


@router.post("/{decision_id}/monitors")
def add_monitor(decision_id: int, payload: MonitorCreate, db: Session = Depends(get_db)):
    decision = _decision_or_404(db, decision_id)
    monitor = ThesisMonitor(decision_id=decision.id, metric=payload.metric, operator=payload.operator,
                            threshold=payload.threshold, rationale=(payload.rationale or "").strip() or None,
                            source="manual")
    db.add(monitor)
    db.flush()
    db.add(DecisionStep(decision_id=decision.id, step_type="monitor_added",
                        content=thesis_monitor.serialize_monitor(monitor)))
    db.commit()
    db.refresh(decision)
    return _detail(decision)


@router.delete("/{decision_id}/monitors/{monitor_id}")
def delete_monitor(decision_id: int, monitor_id: int, db: Session = Depends(get_db)):
    decision = _decision_or_404(db, decision_id)
    monitor = next((m for m in decision.monitors if m.id == monitor_id), None)
    if monitor is None:
        raise HTTPException(status_code=404, detail="找不到這個監控項目。")
    db.add(DecisionStep(decision_id=decision.id, step_type="monitor_removed",
                        content=thesis_monitor.serialize_monitor(monitor)))
    db.delete(monitor)
    db.commit()
    db.refresh(decision)
    return _detail(decision)


@router.get("/{decision_id}/monitors/status")
def monitor_status(decision_id: int, db: Session = Depends(get_db)):
    """Current FinMind values for each monitor, recomputed on every request (FinMind calls are cached)."""
    decision = _decision_or_404(db, decision_id)
    values = thesis_monitor.current_values(decision.ticker, [m.metric for m in decision.monitors])
    return [thesis_monitor.evaluate(m, values[m.metric]) for m in decision.monitors]


@router.get("/meta/metrics")
def metrics():
    return thesis_monitor.METRICS
