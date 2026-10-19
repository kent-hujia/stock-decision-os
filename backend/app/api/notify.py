from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import get_db
from app.models.schemas import JobRun
from app.services import notify
from app.services.claude import as_utc

router = APIRouter()


@router.get("/status")
def status(db: Session = Depends(get_db)):
    runs = db.query(JobRun).filter(JobRun.name == notify.JOB).order_by(JobRun.id.desc()).limit(5).all()
    return {
        "configured": notify.configured(),
        "to": (settings.NOTIFY_EMAIL or settings.GMAIL_USER) or None,
        "check_hour": settings.DAILY_CHECK_HOUR,
        "runs": [{"run_date": r.run_date, "status": r.status, "detail": r.detail,
                  "created_at": as_utc(r.created_at).isoformat() if r.created_at else None} for r in runs],
    }


@router.post("/test")
def test_email():
    try:
        notify.send_email("[波段練習] 測試通知", "這是一封測試信。收到代表每日收盤後的通知已經設定完成。")
    except notify.NotifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"sent": True}


@router.post("/run")
def run_now():
    """Run today's check now (it still only emails when something happened)."""
    return notify.run_once(force=True)
