"""Thesis monitoring: metrics a thesis can be checked against, computed from real FinMind data.

Claude only picks which metric and threshold the thesis implies; the current
values always come from FinMind and are recomputed on every page load.
"""
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from app.models.database import SessionLocal
from app.models.schemas import Decision, DecisionStep, ThesisMonitor
from app.services import claude
from app.services.finmind import FinMindError
from app.services.stock_data import institutional_series, monthly_revenue, quarterly_financials

FLOW_DAYS = 20

METRICS: Dict[str, Dict[str, str]] = {
    "revenue_yoy": {
        "label": "月營收年增率", "unit": "%",
        "description": "最新公布月份的營收，相較去年同月的成長率。",
        "source": "FinMind TaiwanStockMonthRevenue（公開資訊觀測站月營收）",
    },
    "gross_margin": {
        "label": "單季毛利率", "unit": "%",
        "description": "最新一季財報的營業毛利 ÷ 營業收入。",
        "source": "FinMind TaiwanStockFinancialStatements（季報損益表）",
    },
    "institutional_net_buy": {
        "label": f"三大法人近 {FLOW_DAYS} 日買賣超", "unit": "張",
        "description": f"外資、投信、自營商最近 {FLOW_DAYS} 個交易日的合計買賣超張數。",
        "source": "FinMind TaiwanStockInstitutionalInvestorsBuySell（證交所／櫃買中心）",
    },
}
MetricKey = Literal["revenue_yoy", "gross_margin", "institutional_net_buy"]
Operator = Literal[">=", "<="]


def _revenue_yoy(ticker: str) -> Optional[Dict[str, Any]]:
    months = [m for m in monthly_revenue(ticker) if m["yoy"] is not None]
    if not months:
        return None
    m = months[-1]
    return {"value": round(m["yoy"], 2), "as_of": m["period"], "note": f"{m['period']} 月營收"}


def _gross_margin(ticker: str) -> Optional[Dict[str, Any]]:
    quarters = [q for q in quarterly_financials(ticker) if q["gross_profit"] is not None and q["revenue"]]
    if not quarters:
        return None
    q = quarters[-1]
    return {"value": round(q["gross_profit"] / q["revenue"] * 100, 2), "as_of": q["quarter"], "note": f"{q['quarter']} 季報"}


def _institutional(ticker: str) -> Optional[Dict[str, Any]]:
    flows = institutional_series(ticker)[-FLOW_DAYS:]
    if not flows:
        return None
    note = f"{flows[0]['date']} ~ {flows[-1]['date']}，共 {len(flows)} 個交易日"
    return {"value": sum(f["total"] for f in flows), "as_of": flows[-1]["date"], "note": note}


CALCULATORS = {"revenue_yoy": _revenue_yoy, "gross_margin": _gross_margin, "institutional_net_buy": _institutional}


def current_values(ticker: str, metrics) -> Dict[str, Dict[str, Any]]:
    """Latest value of each requested metric; FinMind failures are reported per metric."""
    out = {}
    for key in set(metrics):
        try:
            out[key] = CALCULATORS[key](ticker) or {"error": "FinMind 沒有這項資料（部分產業不適用）。"}
        except FinMindError as e:
            out[key] = {"error": str(e)}
    return out


def evaluate(monitor: ThesisMonitor, current: Dict[str, Any]) -> Dict[str, Any]:
    value = current.get("value")
    holds = None
    if value is not None:
        holds = value >= monitor.threshold if monitor.operator == ">=" else value <= monitor.threshold
    return {**serialize_monitor(monitor), "current": current, "holds": holds}


def serialize_monitor(m: ThesisMonitor) -> Dict[str, Any]:
    meta = METRICS[m.metric]
    return {"id": m.id, "metric": m.metric, "label": meta["label"], "unit": meta["unit"],
            "description": meta["description"], "data_source": meta["source"],
            "operator": m.operator, "threshold": m.threshold, "rationale": m.rationale, "source": m.source}


# --- Claude extraction ---------------------------------------------------------

class MonitorSpec(BaseModel):
    metric: MetricKey
    operator: Operator
    threshold: float
    rationale: str


class MonitorExtraction(BaseModel):
    monitors: List[MonitorSpec]


EXTRACT_PROMPT = """你是協助投資人追蹤投資論點的分析師。以下是投資人對 {ticker} {name} 寫下的投資論點：

<thesis>
{thesis}
</thesis>

系統只能自動追蹤下列指標（括號內是目前的實際數值，供你設定合理門檻）：
{catalog}

請找出論點中「明確提到或直接隱含」、而且能用上述指標檢驗的條件，每個條件轉成一個監控項目：
- metric：上面列出的指標代碼。
- operator 與 threshold：論點成立時應該維持的條件，例如論點說「營收持續雙位數成長」就是 revenue_yoy >= 10；說「毛利率不會跌破 50%」就是 gross_margin >= 50；說「法人持續買超」就是 institutional_net_buy >= 0。單位：百分比指標填百分比數字（10 代表 10%），法人買賣超填張數。
- rationale：用繁體中文一句話說明這個條件對應論點中的哪一句話、跌破代表什麼。
同一個指標最多一項。論點沒有涉及的指標不要硬湊；論點完全沒有可量化的條件時回傳空陣列。"""


def _catalog(ticker: str) -> str:
    values = current_values(ticker, METRICS)
    lines = []
    for key, meta in METRICS.items():
        v = values[key]
        now = f"目前 {v['value']:,}{meta['unit']}（{v['note']}）" if "value" in v else "目前無資料"
        lines.append(f"- {key}：{meta['label']}，{meta['description']}{now}")
    return "\n".join(lines)


def _extract(decision_id: int) -> None:
    db = SessionLocal()
    decision = db.get(Decision, decision_id)
    if decision is None:  # deleted while queued
        db.close()
        return
    try:
        claude.require_key()
        prompt = EXTRACT_PROMPT.format(ticker=decision.ticker, name=decision.stock_name,
                                       thesis=decision.thesis, catalog=_catalog(decision.ticker))
        specs = claude.parse(prompt, MonitorExtraction).monitors
        seen, monitors = set(), []
        for s in specs:
            if s.metric in seen:
                continue
            seen.add(s.metric)
            monitors.append(ThesisMonitor(decision_id=decision.id, metric=s.metric, operator=s.operator,
                                          threshold=s.threshold, rationale=s.rationale, source="ai"))
        # Re-extraction replaces earlier AI monitors but keeps the ones the user added.
        for old in [m for m in decision.monitors if m.source == "ai"]:
            db.delete(old)
        db.add_all(monitors)
        db.flush()
        db.add(DecisionStep(decision_id=decision.id, step_type="monitors_extracted",
                            content={"monitors": [serialize_monitor(m) for m in monitors]}))
        decision.monitor_status, decision.monitor_error = "done", None
    except Exception as e:
        decision.monitor_status, decision.monitor_error = "error", str(e)[:500]
    finally:
        db.commit()
        db.close()


def start_extraction(db, decision: Decision) -> None:
    if decision.monitor_status == "pending" and not claude.is_stale(decision.monitor_started_at):
        return
    decision.monitor_status, decision.monitor_error = "pending", None
    decision.monitor_started_at = datetime.now(timezone.utc)
    db.commit()
    threading.Thread(target=_extract, args=(decision.id,), daemon=True).start()
