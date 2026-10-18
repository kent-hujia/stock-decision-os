"""Claude's plain-language reading of the revenue X-ray, cached per stock per day.

Claude only sees the numbers computed in xray.py and is told not to bring in
outside facts, so every sentence it writes can be traced back to the checks.
"""
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import anthropic
from pydantic import BaseModel

from app.core.config import settings
from app.models.database import SessionLocal
from app.models.schemas import AiReport
from app.services.xray import build_xray

TAIPEI = timezone(timedelta(hours=8))
STALE_AFTER = timedelta(minutes=10)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class XrayReading(BaseModel):
    headline: str
    growth_sources: List[str]
    risks: List[str]
    watch_items: List[str]


PROMPT = """你是專精台股的財報分析師。以下是 {ticker} {name} 的營收品質檢查結果與原始數據（金額單位：億元新台幣）。

{data}

請用繁體中文，只根據上面提供的數字撰寫解讀，不要引用外部新聞、不要臆測沒有給你的資訊；數字不足以下結論時直接說明。
- headline：一句話總結這家公司目前營收成長的「含金量」。
- growth_sources：2-4 點，說明成長主要來自哪裡、證據是哪些數字。
- risks：0-4 點，指出檢查中值得擔心的地方與對應數字；沒有就留空陣列。
- watch_items：2-3 點，未來一兩季應該追蹤哪些具體指標、什麼數字代表情況變好或變壞。
每點 1-2 句，直接寫重點，不要客套話，不要給買賣建議。"""


def today_tw() -> str:
    return datetime.now(TAIPEI).date().isoformat()


def _yi(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(v / 1e8, 1)


def _prompt_data(xray: dict) -> str:
    quarters = [{
        "quarter": q["quarter"],
        "revenue": _yi(q["revenue"]),
        "gross_profit": _yi(q["gross_profit"]),
        "operating_income": _yi(q["operating_income"]),
        "non_operating": _yi(q["non_operating"]),
        "net_income": _yi(q["net_income"]),
        "operating_cash_flow": _yi(q["operating_cash_flow"]),
        "receivables": _yi(q["receivables"]),
        "inventories": _yi(q["inventories"]),
    } for q in xray["quarters"][-8:]]
    months = [{"period": m["period"], "revenue": _yi(m["revenue"]),
               "yoy_pct": None if m["yoy"] is None else round(m["yoy"], 1)}
              for m in xray["monthly_revenue"][-13:]]
    return json.dumps({
        "score": xray["score"],
        "grade": xray["grade"],
        "checks": [{k: c[k] for k in ("title", "status", "value", "detail")} for c in xray["checks"]],
        "quarters": quarters,
        "monthly_revenue": months,
    }, ensure_ascii=False, indent=1)


def _generate(report_id: int, ticker: str, name: str) -> None:
    db = SessionLocal()
    report = db.get(AiReport, report_id)
    try:
        if not settings.ANTHROPIC_API_KEY:
            report.status, report.error = "error", "後端沒有設定 ANTHROPIC_API_KEY。"
            return
        xray = build_xray(ticker)
        response = client.messages.parse(
            model=settings.CLAUDE_MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": PROMPT.format(
                ticker=ticker, name=name, data=_prompt_data(xray))}],
            output_format=XrayReading,
            # Retry on another model automatically if a safety classifier declines.
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise RuntimeError(f"Claude 沒有產生內容（stop_reason={response.stop_reason}）")
        report.content = {**response.parsed_output.model_dump(),
                          "score": xray["score"], "data_as_of": xray["data_as_of"]}
        report.status = "done"
    except anthropic.AuthenticationError:
        report.status, report.error = "error", "ANTHROPIC_API_KEY 無效或沒有設定。"
    except anthropic.RateLimitError:
        report.status, report.error = "error", "Claude API 請求過於頻繁，請稍後再試。"
    except anthropic.APIStatusError as e:
        report.status, report.error = "error", f"Claude API 錯誤（{e.status_code}）：{e.message}"
    except Exception as e:
        report.status, report.error = "error", str(e)[:500]
    finally:
        db.commit()
        db.close()


def latest_report(db, ticker: str) -> Optional[AiReport]:
    return (db.query(AiReport)
            .filter(AiReport.ticker == ticker, AiReport.report_date == today_tw())
            .order_by(AiReport.id.desc()).first())


def start_report(db, ticker: str, name: str) -> AiReport:
    """Reuse today's report if it's done or still running; otherwise start a new one."""
    existing = latest_report(db, ticker)
    if existing and existing.status == "done":
        return existing
    if existing and existing.status == "pending":
        started = existing.created_at
        if started and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started is None or datetime.now(timezone.utc) - started < STALE_AFTER:
            return existing
        existing.status, existing.error = "error", "上一次產生逾時，已重新開始。"
    report = AiReport(ticker=ticker, report_date=today_tw(), status="pending")
    db.add(report)
    db.commit()
    db.refresh(report)
    threading.Thread(target=_generate, args=(report.id, ticker, name), daemon=True).start()
    return report


def serialize(report: Optional[AiReport]) -> dict:
    if report is None:
        return {"status": "none"}
    return {"status": report.status, "report_date": report.report_date,
            "content": report.content, "error": report.error}
