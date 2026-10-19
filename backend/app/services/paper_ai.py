"""Claude on paper trades: a critique of the plan before it runs, and a review after it closes.

Both grade the *process* (was the plan sound, was it followed), not whether the
trade happened to make money, and only use the numbers given to them.
"""
import json
import threading
from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel

from app.core.config import settings
from app.models.database import SessionLocal
from app.models.schemas import PaperTrade
from app.services import claude
from app.services.paper import MISTAKES, event, pnl, r_multiple
from app.services.stock_data import chip_series, institutional_series, price_series


class PlanCritique(BaseModel):
    verdict: Literal["計畫合理", "需要調整", "不建議執行"]
    summary: str
    strengths: List[str]
    risks: List[str]
    plan_issues: List[str]


class TradeReview(BaseModel):
    process_grade: Literal["A", "B", "C", "D"]
    summary: str
    went_well: List[str]
    went_wrong: List[str]
    lesson: str


CRITIQUE_PROMPT = """你是嚴格的台股波段交易教練，負責在下單前挑戰學員的交易計畫。學員在練習波段操作（虛擬資金，真實股價）。

<plan>
{plan}
</plan>

下單當時系統用真實數據做的波段檢查（單位：張、%）：
<checklist>
{checklist}
</checklist>

請用繁體中文，只根據上面的資料評估「這份計畫的品質」，不要預測股價，也不要引用外部資訊：
- verdict：計畫合理／需要調整／不建議執行。
- summary：一兩句總評。
- strengths：0-3 點，計畫中做對的地方。
- risks：1-4 點，檢查清單中與進場理由矛盾、或被忽略的警訊，附數字。
- plan_issues：0-3 點，停損位置、目標價、報酬風險比、部位大小、進場方式是否合理，有問題就直接指出並建議怎麼改。"""

REVIEW_PROMPT = """你是嚴格但公正的台股波段交易教練，負責檢討學員一筆已結束的練習交易（虛擬資金，真實股價）。

<trade>
{trade}
</trade>

進場當時的波段檢查：
<checklist>
{checklist}
</checklist>

從下單日到出場後 10 個交易日的真實日 K（單位：元、張）與籌碼：
<market>
{market}
</market>

學員的自我檢討：
<self_review>
{self_review}
</self_review>

請用繁體中文，只根據上面的資料檢討。重點是「過程」而不是結果：照計畫執行卻停損，可能是好交易；賺錢但違反計畫，可能是壞交易。
- process_grade：A（計畫好且照做）、B（小瑕疵）、C（明顯問題）、D（計畫或執行嚴重失誤）。
- summary：兩三句總評，說明這筆交易輸贏主要是因為判斷、執行，還是運氣。
- went_well：0-3 點。
- went_wrong：0-4 點，附數字（例如進場時已出現的警訊、出場後股價走勢顯示停損或目標是否設得不好）。
- lesson：一句下次可以直接照做的具體規則。
如果學員的自我檢討與數據不符，直接指出。"""


def _plan_dict(t: PaperTrade) -> dict:
    entry_ref = t.limit_price if t.order_type == "limit" else t.ref_price
    risk = entry_ref - t.initial_stop
    return {
        "stock": f"{t.ticker} {t.stock_name}", "thesis": t.thesis,
        "order": "隔日開盤市價買進" if t.order_type == "market" else f"限價 {t.limit_price} 買進",
        "reference_close": {"date": t.ref_date, "price": t.ref_price},
        "stop": t.initial_stop, "target": t.target_price, "shares": t.shares,
        "risk_per_share": round(risk, 2), "total_risk": round(risk * t.shares),
        "reward_risk_ratio": round((t.target_price - entry_ref) / risk, 2) if risk > 0 else None,
        "position_value": round(entry_ref * t.shares),
    }


def _checklist_text(t: PaperTrade) -> str:
    c = t.checklist or {}
    return json.dumps({"checks": [{k: x[k] for k in ("title", "status", "value", "detail")} for x in c.get("checks", [])],
                       "defense": c.get("defense")}, ensure_ascii=False, indent=1)


def _market_text(t: PaperTrade) -> str:
    bars = price_series(t.ticker)
    dates = [b["date"] for b in bars]
    start = next((i for i, d in enumerate(dates) if d > t.plan_date), len(dates))
    end = next((i for i, d in enumerate(dates) if d > (t.exit_date or "9999")), len(dates))
    window = bars[max(0, start - 1):min(len(bars), end + 10)]
    chips = {c["date"]: c for c in chip_series(t.ticker)}
    flows = {f["date"]: f for f in institutional_series(t.ticker)}
    rows = []
    for b in window:
        c, f = chips.get(b["date"], {}), flows.get(b["date"], {})
        rows.append({"date": b["date"], "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"],
                     "volume": b["volume_lots"], "foreign": f.get("foreign"), "trust": f.get("trust"),
                     "margin": c.get("margin_balance"),
                     "phase": "持有中" if t.entry_date and t.entry_date <= b["date"] <= (t.exit_date or "9999")
                     else ("出場後" if t.exit_date and b["date"] > t.exit_date else "進場前")})
    return json.dumps(rows, ensure_ascii=False)


def _trade_text(t: PaperTrade) -> str:
    stop_moves = [e.content for e in t.events if e.event_type == "stop_moved"]
    return json.dumps({
        **_plan_dict(t),
        "entry": {"date": t.entry_date, "price": t.entry_price},
        "exit": {"date": t.exit_date, "price": t.exit_price, "reason": t.exit_reason},
        "stop_moves": stop_moves, "highest_while_held": t.high_since_entry, "lowest_while_held": t.low_since_entry,
        "pnl_after_costs": round(pnl(t) or 0), "r_multiple": None if r_multiple(t) is None else round(r_multiple(t), 2),
    }, ensure_ascii=False, indent=1)


def _self_review_text(t: PaperTrade) -> str:
    if not t.reviewed_at:
        return "學員還沒有寫自我檢討。"
    return json.dumps({"followed_plan": t.followed_plan,
                       "mistakes": [MISTAKES.get(m, m) for m in t.mistakes or []],
                       "lesson": t.lesson}, ensure_ascii=False)


JOBS = {
    "critique": (lambda t: CRITIQUE_PROMPT.format(plan=json.dumps(_plan_dict(t), ensure_ascii=False, indent=1),
                                                  checklist=_checklist_text(t)),
                 PlanCritique, lambda: settings.CLAUDE_MODEL, "plan_critiqued"),
    "ai_review": (lambda t: REVIEW_PROMPT.format(trade=_trade_text(t), checklist=_checklist_text(t),
                                                 market=_market_text(t), self_review=_self_review_text(t)),
                  TradeReview, lambda: settings.REVIEW_MODEL, "ai_reviewed"),
}


def _run(trade_id: int, job: str) -> None:
    build_prompt, output, model, event_type = JOBS[job]
    db = SessionLocal()
    t = db.get(PaperTrade, trade_id)
    if t is None:
        db.close()
        return
    try:
        claude.require_key()
        result = claude.parse(build_prompt(t), output, model=model())
        setattr(t, job, {**result.model_dump(), "model": model()})
        setattr(t, f"{job}_status", "done")
        event(db, t, event_type, result.model_dump())
    except Exception as e:
        setattr(t, f"{job}_status", "error")
        setattr(t, f"{job}_error", str(e)[:500])
    finally:
        db.commit()
        db.close()


def start(db, t: PaperTrade, job: str) -> None:
    if getattr(t, f"{job}_status") == "pending" and not claude.is_stale(getattr(t, f"{job}_started_at")):
        return
    setattr(t, f"{job}_status", "pending")
    setattr(t, f"{job}_error", None)
    setattr(t, f"{job}_started_at", datetime.now(timezone.utc))
    db.commit()
    threading.Thread(target=_run, args=(t.id, job), daemon=True).start()
