"""AI skeptic: Claude challenges a thesis with the stock's real X-ray numbers, then grades rebuttals.

Claude only sees the thesis, the X-ray checks and a few market numbers computed
from FinMind, and is told not to bring in outside facts. Nothing falls back to
canned questions: if Claude or FinMind fails, the user sees the error.
"""
import json
import threading
from typing import Any, Dict, List, Literal

from pydantic import BaseModel

from app.models.database import SessionLocal
from app.models.schemas import Decision, DecisionStep, SkepticAnswer, SkepticReview
from app.services import claude
from app.services.ai_report import prompt_data
from app.services.stock_data import institutional_series, price_series
from app.services.xray import build_xray

RISK_TYPES = ("基本面", "產業與總經", "評價與執行")


class SkepticQuestion(BaseModel):
    risk_type: Literal["基本面", "產業與總經", "評價與執行"]
    question: str
    evidence: str


class SkepticQuestions(BaseModel):
    questions: List[SkepticQuestion]


class RebuttalGrade(BaseModel):
    verdict: Literal["Pass", "Fail"]
    reason: str


QUESTION_PROMPT = """你是一位嚴厲、講求證據的避險基金放空研究員。投資人想買進 {ticker} {name}，以下是投資人寫下的論點（信心 {conviction}/10）：

<thesis>
{thesis}
</thesis>

以下是這檔股票的真實數據：營收品質檢查結果、季報與月營收（金額單位：億元新台幣），以及股價與法人買賣超：
<data>
{data}
</data>

請用繁體中文提出 3 個最能動搖這個論點的質疑問題，三題的 risk_type 依序是「基本面」「產業與總經」「評價與執行」各一題。
- question：直接、具體、一針見血，針對論點裡最脆弱的假設，讓投資人必須用證據回答，不要客套。
- evidence：這個問題依據的具體數字（引用上面資料中的期間與數值）。資料中沒有相關數字時，寫明「資料中沒有直接證據」，並說明問題是從論點的哪個假設推出來的。
只能使用上面提供的數據，不要引用外部新聞或你記得的公司資訊。"""

GRADE_PROMPT = """你是一位嚴厲、講求證據的避險基金放空研究員。你對 {ticker} {name} 的投資論點提出了質疑，現在要評分投資人的反駁。

<thesis>
{thesis}
</thesis>

你的質疑（{risk_type}）：
<question>
{question}
</question>
你提問時依據的數據：{evidence}

投資人的反駁：
<rebuttal>
{rebuttal}
</rebuttal>

可用來查核反駁內容的真實數據（金額單位：億元新台幣）：
<data>
{data}
</data>

評分標準：
- Pass：反駁直接回應了質疑的核心，並提出具體證據、數字或可驗證的理由，而且與上面的數據沒有矛盾。
- Fail：迴避問題、只有樂觀信念或空泛說法、沒有證據，或與上面的數據矛盾。
reason 用繁體中文寫 2-3 句，直接指出反駁哪裡站得住、哪裡站不住；若引用數據請寫出數字。不要給買賣建議。"""


def _market_data(ticker: str, quarters: List[Dict[str, Any]]) -> Dict[str, Any]:
    prices = price_series(ticker)
    flows = institutional_series(ticker)[-20:]
    out: Dict[str, Any] = {}
    if prices:
        last = prices[-1]
        year = prices[-250:]
        out["price"] = {"date": last["date"], "close": last["close"],
                        "high_52w": max(p["high"] for p in year), "low_52w": min(p["low"] for p in year)}
        eps = [q["eps"] for q in quarters[-4:]]
        if len(eps) == 4 and all(e is not None for e in eps):
            ttm = round(sum(eps), 2)
            out["trailing_4q_eps"] = ttm
            out["trailing_pe"] = round(last["close"] / ttm, 1) if ttm > 0 else None
    if flows:
        out["institutional_net_buy_lots_20d"] = {
            "from": flows[0]["date"], "to": flows[-1]["date"],
            **{k: sum(f[k] for f in flows) for k in ("foreign", "trust", "dealer", "total")},
        }
    return out


def stock_context(ticker: str) -> Dict[str, Any]:
    """Real numbers Claude may use, plus the as-of dates shown to the user."""
    xray = build_xray(ticker)
    data = json.loads(prompt_data(xray))
    data["market"] = _market_data(ticker, xray["quarters"])
    return {"text": json.dumps(data, ensure_ascii=False, indent=1), "data_as_of": xray["data_as_of"]}


def _generate(review_id: int) -> None:
    db = SessionLocal()
    review = db.get(SkepticReview, review_id)
    if review is None:
        db.close()
        return
    decision = db.get(Decision, review.decision_id)
    try:
        claude.require_key()
        ctx = stock_context(decision.ticker)
        result = claude.parse(QUESTION_PROMPT.format(
            ticker=decision.ticker, name=decision.stock_name, conviction=decision.conviction,
            thesis=decision.thesis, data=ctx["text"]), SkepticQuestions)
        by_type = {q.risk_type: q for q in result.questions}
        if any(t not in by_type for t in RISK_TYPES):
            raise claude.ClaudeError("Claude 沒有產生完整的三類質疑問題，請重新產生。")
        review.questions = [by_type[t].model_dump() for t in RISK_TYPES]
        review.data_as_of = ctx["data_as_of"]
        review.status = "done"
        db.add(DecisionStep(decision_id=decision.id, step_type="skeptic_questions",
                            content={"review_id": review.id, "questions": review.questions,
                                     "data_as_of": review.data_as_of}))
    except Exception as e:
        review.status, review.error = "error", str(e)[:500]
    finally:
        db.commit()
        db.close()


def start_review(db, decision: Decision, regenerate: bool = False) -> SkepticReview:
    """Reuse the latest review if it's done or still running, unless asked for new questions."""
    latest = decision.reviews[-1] if decision.reviews else None
    if latest and latest.status == "pending" and not claude.is_stale(latest.created_at):
        return latest
    if latest and latest.status == "done" and not regenerate:
        return latest
    if latest and latest.status == "pending":
        latest.status, latest.error = "error", "上一次產生逾時，已重新開始。"
    review = SkepticReview(decision_id=decision.id, status="pending")
    db.add(review)
    db.commit()
    db.refresh(review)
    threading.Thread(target=_generate, args=(review.id,), daemon=True).start()
    return review


def _grade(answer_id: int) -> None:
    db = SessionLocal()
    answer = db.get(SkepticAnswer, answer_id)
    if answer is None:
        db.close()
        return
    review = db.get(SkepticReview, answer.review_id)
    decision = db.get(Decision, review.decision_id)
    q = review.questions[answer.question_index]
    try:
        claude.require_key()
        ctx = stock_context(decision.ticker)
        grade = claude.parse(GRADE_PROMPT.format(
            ticker=decision.ticker, name=decision.stock_name, thesis=decision.thesis,
            risk_type=q["risk_type"], question=q["question"], evidence=q["evidence"],
            rebuttal=answer.rebuttal, data=ctx["text"]), RebuttalGrade)
        answer.verdict, answer.reason, answer.status = grade.verdict, grade.reason, "done"
        db.add(DecisionStep(decision_id=decision.id, step_type="rebuttal_graded", content={
            "review_id": review.id, "question_index": answer.question_index,
            "risk_type": q["risk_type"], "question": q["question"], "rebuttal": answer.rebuttal,
            "verdict": grade.verdict, "reason": grade.reason}))
    except Exception as e:
        answer.status, answer.error = "error", str(e)[:500]
    finally:
        db.commit()
        db.close()


def submit_answer(db, review: SkepticReview, question_index: int, rebuttal: str) -> SkepticAnswer:
    answer = SkepticAnswer(review_id=review.id, question_index=question_index, rebuttal=rebuttal, status="pending")
    db.add(answer)
    db.commit()
    db.refresh(answer)
    threading.Thread(target=_grade, args=(answer.id,), daemon=True).start()
    return answer
