from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.stocks import _stock_or_404
from app.models.database import get_db
from app.models.schemas import PaperTrade
from app.services import paper, paper_ai
from app.services.claude import as_utc
from app.services.finmind import FinMindError
from app.services.swing import build_swing

router = APIRouter()

ACTIVE = ("planned", "open")


class TradeCreate(BaseModel):
    ticker: str = Field(..., max_length=10)
    thesis: str = Field(..., min_length=10, max_length=2000)
    order_type: Literal["market", "limit"]
    limit_price: Optional[float] = Field(None, gt=0)
    stop_price: float = Field(..., gt=0)
    target_price: float = Field(..., gt=0)
    shares: int = Field(..., gt=0)


class TradeUpdate(BaseModel):
    stop_price: Optional[float] = Field(None, gt=0)
    target_price: Optional[float] = Field(None, gt=0)
    note: Optional[str] = Field(None, max_length=500)


class TradeReviewIn(BaseModel):
    followed_plan: bool
    mistakes: List[str] = []
    lesson: str = Field(..., min_length=1, max_length=2000)


class AccountUpdate(BaseModel):
    initial_cash: Optional[float] = Field(None, ge=100_000, le=100_000_000)
    risk_pct: Optional[float] = Field(None, gt=0, le=10)


def _iso(dt) -> Optional[str]:
    dt = as_utc(dt)
    return dt.isoformat() if dt else None


def _sync(db: Session) -> None:
    try:
        paper.sync_all(db)
    except FinMindError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _trade_or_404(db: Session, trade_id: int) -> PaperTrade:
    t = db.get(PaperTrade, trade_id)
    if not t:
        raise HTTPException(status_code=404, detail="找不到這筆交易。")
    return t


def _summary(t: PaperTrade, last: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    entry_ref = t.entry_price or (t.limit_price if t.order_type == "limit" else t.ref_price)
    out = {
        "id": t.id, "ticker": t.ticker, "stock_name": t.stock_name, "status": t.status,
        "order_type": t.order_type, "limit_price": t.limit_price, "ref_price": t.ref_price, "ref_date": t.ref_date,
        "plan_date": t.plan_date, "shares": t.shares, "initial_stop": t.initial_stop, "stop_price": t.stop_price,
        "target_price": t.target_price, "entry_date": t.entry_date, "entry_price": t.entry_price,
        "exit_date": t.exit_date, "exit_price": t.exit_price, "exit_reason": t.exit_reason,
        "exit_requested_date": t.exit_requested_date, "cancel_reason": t.cancel_reason,
        "risk_amount": round((entry_ref - t.initial_stop) * t.shares),
        "reward_risk": round((t.target_price - entry_ref) / (entry_ref - t.initial_stop), 2) if entry_ref > t.initial_stop else None,
        "pnl": None if paper.pnl(t) is None else round(paper.pnl(t)),
        "r_multiple": None if paper.r_multiple(t) is None else round(paper.r_multiple(t), 2),
        "reviewed": t.reviewed_at is not None, "created_at": _iso(t.created_at),
    }
    if t.status == "open" and last:
        out["last_close"] = {"date": last["date"], "price": last["close"]}
        out["unrealized"] = round((last["close"] - t.entry_price) * t.shares)
        out["unrealized_r"] = round((last["close"] - t.entry_price) / (t.entry_price - t.initial_stop), 2) \
            if t.entry_price > t.initial_stop else None
    return out


def _detail(t: PaperTrade) -> Dict[str, Any]:
    last = paper.last_close(t.ticker) if t.status == "open" else None
    return {
        **_summary(t, last), "thesis": t.thesis, "checklist": t.checklist,
        "high_since_entry": t.high_since_entry, "low_since_entry": t.low_since_entry,
        "followed_plan": t.followed_plan, "mistakes": t.mistakes or [], "lesson": t.lesson,
        "critique_status": t.critique_status, "critique": t.critique, "critique_error": t.critique_error,
        "ai_review_status": t.ai_review_status, "ai_review": t.ai_review, "ai_review_error": t.ai_review_error,
        "events": [{"id": e.id, "event_type": e.event_type, "bar_date": e.bar_date, "content": e.content,
                    "created_at": _iso(e.created_at)} for e in reversed(t.events)],
    }


@router.get("/account")
def account(db: Session = Depends(get_db)):
    _sync(db)
    trades = db.query(PaperTrade).order_by(PaperTrade.id.desc()).all()
    lasts = {}
    for t in trades:
        if t.status == "open" and t.ticker not in lasts:
            lasts[t.ticker] = paper.last_close(t.ticker)
    return {
        "account": paper.account_summary(db),
        "stats": paper.stats(db),
        "trades": [_summary(t, lasts.get(t.ticker)) for t in trades],
        "mistake_options": paper.MISTAKES,
    }


@router.patch("/account")
def update_account(payload: AccountUpdate, db: Session = Depends(get_db)):
    acc = paper.get_account(db)
    if payload.initial_cash is not None:
        if db.query(PaperTrade).filter(PaperTrade.status.in_(("open", "closed"))).count():
            raise HTTPException(status_code=409, detail="已經有成交紀錄，不能再修改初始資金。")
        acc.initial_cash = payload.initial_cash
    if payload.risk_pct is not None:
        acc.risk_pct = payload.risk_pct
    db.commit()
    return paper.account_summary(db)


@router.post("/trades")
def create_trade(payload: TradeCreate, db: Session = Depends(get_db)):
    stock = _stock_or_404(payload.ticker)
    _sync(db)
    try:
        swing = build_swing(stock["stock_id"])
    except FinMindError as e:
        raise HTTPException(status_code=502, detail=str(e))
    defense = swing["defense"]
    if not defense:
        raise HTTPException(status_code=400, detail="這檔股票的股價資料不足，無法建立交易計畫。")
    if payload.order_type == "limit" and not payload.limit_price:
        raise HTTPException(status_code=400, detail="限價單需要填寫限價。")
    entry_ref = payload.limit_price if payload.order_type == "limit" else defense["close"]
    if payload.stop_price >= entry_ref:
        raise HTTPException(status_code=400, detail=f"停損價必須低於進場參考價 {entry_ref:g}。")
    if payload.target_price <= entry_ref:
        raise HTTPException(status_code=400, detail=f"目標價必須高於進場參考價 {entry_ref:g}。")
    summary = paper.account_summary(db)
    risk = (entry_ref - payload.stop_price) * payload.shares
    if risk > summary["risk_budget"] * 1.001:
        raise HTTPException(status_code=400, detail=(
            f"這筆最多可能虧 {risk:,.0f} 元，超過每筆風險上限 {summary['risk_budget']:,} 元"
            f"（總資產 {summary['equity']:,} 元的 {summary['risk_pct']:g}%）。請減少股數或把停損拉近。"))
    cost = entry_ref * payload.shares * 1.03
    if cost > summary["available"]:
        raise HTTPException(status_code=400, detail=f"可用資金 {summary['available']:,} 元不足（預留跳空 3% 需 {cost:,.0f} 元）。")
    t = PaperTrade(
        ticker=stock["stock_id"], stock_name=stock["name"], status="planned", thesis=payload.thesis.strip(),
        order_type=payload.order_type, limit_price=payload.limit_price if payload.order_type == "limit" else None,
        ref_price=defense["close"], ref_date=defense["date"], plan_date=paper.plan_date_now(),
        initial_stop=payload.stop_price, stop_price=payload.stop_price, target_price=payload.target_price,
        shares=payload.shares,
        checklist={"checks": swing["checks"], "defense": defense, "data_as_of": swing["data_as_of"]},
    )
    db.add(t)
    db.flush()
    paper.event(db, t, "planned", {"order_type": t.order_type, "limit_price": t.limit_price, "stop": t.stop_price,
                                   "target": t.target_price, "shares": t.shares, "ref_price": t.ref_price})
    db.commit()
    return _detail(t)


@router.get("/trades/{trade_id}")
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    t = _trade_or_404(db, trade_id)
    if t.status in ACTIVE:
        _sync(db)
        db.refresh(t)
    return _detail(t)


@router.patch("/trades/{trade_id}")
def update_trade(trade_id: int, payload: TradeUpdate, db: Session = Depends(get_db)):
    t = _trade_or_404(db, trade_id)
    if t.status not in ACTIVE:
        raise HTTPException(status_code=409, detail="只有未成交或持有中的交易可以調整。")
    note = (payload.note or "").strip() or None
    if payload.stop_price is not None and payload.stop_price != t.stop_price:
        if payload.stop_price >= t.target_price:
            raise HTTPException(status_code=400, detail="停損價必須低於目標價。")
        if t.status == "planned":
            entry_ref = paper.order_price(t)
            budget = paper.account_summary(db)["risk_budget"]
            if payload.stop_price >= entry_ref:
                raise HTTPException(status_code=400, detail=f"停損價必須低於進場參考價 {entry_ref:g}。")
            if (entry_ref - payload.stop_price) * t.shares > budget * 1.001:
                raise HTTPException(status_code=400, detail=f"新停損會讓這筆最多虧損超過每筆風險上限 {budget:,} 元。")
        paper.event(db, t, "stop_moved", {"from": t.stop_price, "to": payload.stop_price, "note": note})
        t.stop_price = payload.stop_price
        if t.status == "planned":
            t.initial_stop = payload.stop_price
    if payload.target_price is not None and payload.target_price != t.target_price:
        if payload.target_price <= t.stop_price:
            raise HTTPException(status_code=400, detail="目標價必須高於停損價。")
        paper.event(db, t, "target_moved", {"from": t.target_price, "to": payload.target_price, "note": note})
        t.target_price = payload.target_price
    db.commit()
    return _detail(t)


@router.post("/trades/{trade_id}/cancel")
def cancel_trade(trade_id: int, db: Session = Depends(get_db)):
    t = _trade_or_404(db, trade_id)
    if t.status != "planned":
        raise HTTPException(status_code=409, detail="只有尚未成交的委託可以取消。")
    t.status, t.cancel_reason = "cancelled", "manual"
    paper.event(db, t, "cancelled", {"reason": "手動取消委託"})
    db.commit()
    return _detail(t)


@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    """Only orders that never filled can be deleted, so the track record can't be edited."""
    t = _trade_or_404(db, trade_id)
    if t.status not in ("planned", "cancelled"):
        raise HTTPException(status_code=409, detail="已成交的交易不能刪除，成績紀錄要完整保留。")
    db.delete(t)
    db.commit()
    return {"deleted": True}


@router.post("/trades/{trade_id}/exit")
def exit_trade(trade_id: int, db: Session = Depends(get_db)):
    t = _trade_or_404(db, trade_id)
    if t.status != "open":
        raise HTTPException(status_code=409, detail="只有持有中的部位可以出場。")
    if not t.exit_requested_date:
        t.exit_requested_date = paper.plan_date_now()
        paper.event(db, t, "exit_requested", {"note": "下一個交易日開盤市價賣出"})
        db.commit()
    return _detail(t)


@router.post("/trades/{trade_id}/review")
def review_trade(trade_id: int, payload: TradeReviewIn, db: Session = Depends(get_db)):
    t = _trade_or_404(db, trade_id)
    if t.status != "closed":
        raise HTTPException(status_code=409, detail="交易結束後才能檢討。")
    unknown = [m for m in payload.mistakes if m not in paper.MISTAKES]
    if unknown:
        raise HTTPException(status_code=400, detail=f"未知的錯誤類型：{'、'.join(unknown)}")
    t.followed_plan, t.mistakes, t.lesson = payload.followed_plan, payload.mistakes, payload.lesson.strip()
    t.reviewed_at = paper.now_utc()
    paper.event(db, t, "reviewed", {"followed_plan": t.followed_plan,
                                    "mistakes": [paper.MISTAKES[m] for m in t.mistakes], "lesson": t.lesson})
    db.commit()
    return _detail(t)


@router.post("/trades/{trade_id}/critique")
def critique_trade(trade_id: int, db: Session = Depends(get_db)):
    t = _trade_or_404(db, trade_id)
    paper_ai.start(db, t, "critique")
    return _detail(t)


@router.post("/trades/{trade_id}/ai-review")
def ai_review_trade(trade_id: int, db: Session = Depends(get_db)):
    t = _trade_or_404(db, trade_id)
    if t.status != "closed":
        raise HTTPException(status_code=409, detail="交易結束後才能請 AI 檢討。")
    paper_ai.start(db, t, "ai_review")
    return _detail(t)
