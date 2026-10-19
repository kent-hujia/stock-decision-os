"""Claude reads an uploaded earnings-call (法說會) PDF and breaks down where revenue growth comes from.

The deck is the company's own claims; Claude also gets the stock's real reported
numbers so it can point out where the slides and the filings disagree.
"""
import base64
import threading
from typing import List, Optional

from pydantic import BaseModel

from app.core.config import settings
from app.models.database import SessionLocal
from app.models.schemas import EarningsCall
from app.services import claude
from app.services.ai_report import prompt_data
from app.services.xray import build_xray

MAX_BYTES = 20 * 1024 * 1024


class Segment(BaseModel):
    name: str
    share_pct: Optional[float]
    trend: str
    note: str


class CallBreakdown(BaseModel):
    period: str
    headline: str
    segments: List[Segment]
    growth_drivers: List[str]
    one_off_items: List[str]
    guidance: List[str]
    risks: List[str]
    consistency: List[str]


PROMPT = """附件是 {ticker} {name} 的法說會簡報。以下是這家公司在財報中實際申報的數字（金額單位：億元新台幣），用來交叉核對：

<reported>
{data}
</reported>

請用繁體中文拆解這份簡報，只根據簡報內容與上面的申報數字，不要引用外部資訊；簡報沒提到的就留空，不要推測：
- period：簡報涵蓋的期間（例如 2026Q2）。
- headline：一句話說明這一季營收成長主要從哪裡來。
- segments：依產品線、應用別、技術製程或地區列出營收組成。share_pct 填營收占比（%），簡報沒寫就填 null；trend 寫成長、持平、衰退，或簡報給的季增、年增數字；note 用一句話說明。
- growth_drivers：1-4 點，成長的具體來源（產品、客戶、價格、產能），附簡報中的數字。
- one_off_items：一次性或不可持續的因素，例如匯率、處分利益、補助、存貨回沖、遞延營收；沒有就留空陣列。
- guidance：公司對下一季或全年的展望與數字。
- risks：0-4 點，簡報中提到或從數字看得出的風險。
- consistency：0-3 點，簡報說法與申報數字是否一致，例如毛利率、營收成長率；不一致就直接指出。"""


def _generate(call_id: int, name: str) -> None:
    db = SessionLocal()
    call = db.get(EarningsCall, call_id)
    if call is None:
        db.close()
        return
    try:
        claude.require_key()
        data = prompt_data(build_xray(call.ticker))
        content = [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.standard_b64encode(call.pdf).decode()}},
            {"type": "text", "text": PROMPT.format(ticker=call.ticker, name=name, data=data)},
        ]
        result = claude.parse(content, CallBreakdown, model=settings.PDF_MODEL)
        call.content = {**result.model_dump(), "model": settings.PDF_MODEL}
        call.status, call.error = "done", None
    except Exception as e:
        call.status, call.error = "error", str(e)[:500]
    finally:
        db.commit()
        db.close()


def start(db, call: EarningsCall, name: str) -> None:
    call.status, call.error = "pending", None
    db.commit()
    threading.Thread(target=_generate, args=(call.id, name), daemon=True).start()


def serialize(call: EarningsCall) -> dict:
    created = claude.as_utc(call.created_at)
    return {"id": call.id, "filename": call.filename, "size": call.size, "status": call.status,
            "content": call.content, "error": call.error, "created_at": created.isoformat() if created else None}
