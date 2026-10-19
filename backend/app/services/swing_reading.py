"""Claude's daily plain-language reading of the swing checklist (technical + chips), on a cheap model."""
import json
import threading
from typing import List, Optional

from pydantic import BaseModel

from app.core.config import settings
from app.models.database import SessionLocal
from app.models.schemas import AiReading
from app.services import claude
from app.services.ai_report import today_tw
from app.services.swing import build_swing

KIND = "swing"


class SwingReading(BaseModel):
    headline: str
    chips: List[str]
    technical: List[str]
    watch_items: List[str]


PROMPT = """你是專精台股籌碼與技術面的波段交易教練。以下是 {ticker} {name} 的波段檢查結果與近期原始數據
（成交量、融資、融券、借券賣出單位為張；外資持股與當沖比為 %；法人買賣超為張）。

{data}

請用繁體中文，只根據上面的數字撰寫解讀，不要引用外部新聞或你記得的公司資訊：
- headline：一句話說明目前籌碼與技術面的整體狀態（例如「法人與散戶籌碼方向相反，趨勢仍在整理」）。
- chips：2-4 點，解讀主力與散戶籌碼的變化（外資、投信、融資、借券賣出、外資持股、當沖），指出彼此是否矛盾，附上數字。
- technical：1-3 點，解讀趨勢、量能與防守點。
- watch_items：2-3 點，接下來幾天要盯哪個具體數字、出現什麼變化代表轉強或轉弱。
每點 1-2 句。這是給投資人練習判斷用的，不要直接叫人買進或賣出。"""


def _prompt_data(swing: dict) -> str:
    return json.dumps({
        "checks": [{k: c[k] for k in ("title", "status", "value", "detail")} for c in swing["checks"]],
        "defense": swing["defense"],
        "recent_prices": [{k: p[k] for k in ("date", "close", "volume_lots", "ma20", "ma60")}
                          for p in swing["prices"][-10:]],
        "recent_chips": swing["chips"][-10:],
        "recent_institutional": swing["institutional"][-10:],
    }, ensure_ascii=False, indent=1)


def _generate(reading_id: int, ticker: str, name: str) -> None:
    db = SessionLocal()
    reading = db.get(AiReading, reading_id)
    try:
        claude.require_key()
        swing = build_swing(ticker)
        result = claude.parse(PROMPT.format(ticker=ticker, name=name, data=_prompt_data(swing)),
                              SwingReading, effort="low", model=settings.SWING_MODEL)
        reading.content = {**result.model_dump(), "data_as_of": swing["data_as_of"], "model": settings.SWING_MODEL}
        reading.status = "done"
    except Exception as e:
        reading.status, reading.error = "error", str(e)[:500]
    finally:
        db.commit()
        db.close()


def latest(db, ticker: str) -> Optional[AiReading]:
    return (db.query(AiReading)
            .filter(AiReading.kind == KIND, AiReading.ticker == ticker, AiReading.report_date == today_tw())
            .order_by(AiReading.id.desc()).first())


def start(db, ticker: str, name: str) -> AiReading:
    """Reuse today's reading if it's done or still running; otherwise start a new one."""
    existing = latest(db, ticker)
    if existing and (existing.status == "done"
                     or (existing.status == "pending" and not claude.is_stale(existing.created_at))):
        return existing
    if existing and existing.status == "pending":
        existing.status, existing.error = "error", "上一次產生逾時，已重新開始。"
    reading = AiReading(kind=KIND, ticker=ticker, report_date=today_tw(), status="pending")
    db.add(reading)
    db.commit()
    db.refresh(reading)
    threading.Thread(target=_generate, args=(reading.id, ticker, name), daemon=True).start()
    return reading


def serialize(reading: Optional[AiReading]) -> dict:
    if reading is None:
        return {"status": "none"}
    return {"status": reading.status, "report_date": reading.report_date,
            "content": reading.content, "error": reading.error}
