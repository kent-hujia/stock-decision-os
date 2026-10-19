"""Daily after-close check of paper trades, with an email summary through Gmail.

Runs in a background thread inside the web process: every 15 minutes it checks
whether today's (Taiwan) run is due and not yet done. Nothing is sent when
nothing happened, so holidays stay quiet.
"""
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any, Dict, List

from app.core.config import settings
from app.models.database import SessionLocal
from app.models.schemas import JobRun, PaperTrade, PaperTradeEvent
from app.services import paper
from app.services.ai_report import TAIPEI, today_tw
from app.services.stock_data import institutional_series, price_series
from app.services.swing import _streak, moving_average

JOB = "daily_check"
EVENT_TEXT = {
    "filled": lambda e: f"成交買進 {e.content['shares']:,} 股 @ {e.content['price']:g}",
    "closed": lambda e: {"stop": "觸發停損", "target": "達到目標價", "manual": "手動出場"}[e.content["reason"]]
    + f" @ {e.content['price']:g}，損益 {e.content['pnl']:+,.0f} 元"
    + ("" if e.content.get("r") is None else f"（{e.content['r']:+.2f}R）"),
    "cancelled": lambda e: f"委託取消：{e.content['reason']}",
    "alert": lambda e: f"警示：{e.content['message']}",
}


class NotifyError(Exception):
    pass


def configured() -> bool:
    return bool(settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD)


def send_email(subject: str, body: str) -> None:
    if not configured():
        raise NotifyError("後端沒有設定 GMAIL_USER 與 GMAIL_APP_PASSWORD。")
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.GMAIL_USER
    msg["To"] = settings.NOTIFY_EMAIL or settings.GMAIL_USER
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise NotifyError("Gmail 登入失敗，請確認 GMAIL_USER 與應用程式密碼。") from e
    except (smtplib.SMTPException, OSError) as e:
        raise NotifyError(f"寄信失敗：{e}") from e


def _alert(db, t: PaperTrade, kind: str, bar_date: str, message: str) -> None:
    exists = db.query(PaperTradeEvent).filter(PaperTradeEvent.trade_id == t.id, PaperTradeEvent.event_type == "alert",
                                              PaperTradeEvent.bar_date == bar_date).all()
    if any(e.content.get("kind") == kind for e in exists):
        return
    paper.event(db, t, "alert", {"kind": kind, "message": message}, bar_date)


def check_alerts(db, t: PaperTrade) -> None:
    """Warnings for an open position on its latest bar (each fires once per bar)."""
    bars = price_series(t.ticker)
    if len(bars) < 21:
        return
    last, prev = bars[-1], bars[-2]
    closes = [b["close"] for b in bars]
    ma20, ma20_prev = moving_average(closes, 20), moving_average(closes, 20, len(closes) - 1)
    if last["close"] < ma20 and prev["close"] >= ma20_prev:
        _alert(db, t, "below_ma20", last["date"], f"收盤 {last['close']:g} 跌破 20 日均線 {ma20:.1f}")
    if last["close"] <= t.stop_price * 1.03:
        _alert(db, t, "near_stop", last["date"],
               f"收盤 {last['close']:g} 距停損 {t.stop_price:g} 不到 3%")
    flows = institutional_series(t.ticker)
    if flows and flows[-1]["date"] == last["date"]:
        streak = _streak([f["foreign"] for f in flows[-20:]])
        if streak == -3:
            _alert(db, t, "foreign_selling", last["date"], "外資連續賣超 3 天")


def daily_check(db) -> Dict[str, Any]:
    """Sync all trades, add alerts, and email what happened. Returns a summary."""
    start_id = db.query(PaperTradeEvent.id).order_by(PaperTradeEvent.id.desc()).limit(1).scalar() or 0
    paper.sync_all(db)
    for t in db.query(PaperTrade).filter(PaperTrade.status == "open"):
        check_alerts(db, t)
    db.commit()
    new = (db.query(PaperTradeEvent).filter(PaperTradeEvent.id > start_id, PaperTradeEvent.event_type.in_(EVENT_TEXT))
           .order_by(PaperTradeEvent.id).all())
    lines: List[str] = []
    for e in new:
        t = db.get(PaperTrade, e.trade_id)
        lines.append(f"・{t.stock_name} {t.ticker}（{e.bar_date}）：{EVENT_TEXT[e.event_type](e)}")
    summary = {"events": len(new), "emailed": False}
    if lines:
        acc = paper.account_summary(db)
        unreviewed = paper.stats(db)["unreviewed"]
        body = "\n".join([
            "今天收盤後的模擬交易更新：", "", *lines, "",
            f"總資產 {acc['equity']:,} 元（{acc['return_pct']:+.2f}%），現金 {acc['cash']:,} 元。",
            *([f"還有 {unreviewed} 筆已結束的交易沒有檢討。"] if unreviewed else []),
            "", "這是虛擬資金的練習帳戶，股價為真實收盤資料。",
        ])
        send_email(f"[波段練習] {today_tw()} {len(lines)} 則更新", body)
        summary["emailed"] = True
    return summary


def run_once(force: bool = False) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        today = today_tw()
        if not force and db.query(JobRun).filter(JobRun.name == JOB, JobRun.run_date == today,
                                                 JobRun.status == "done").count():
            return {"skipped": True}
        try:
            result = daily_check(db)
            db.add(JobRun(name=JOB, run_date=today, status="done", detail=result))
        except Exception as e:
            db.rollback()
            result = {"error": str(e)[:500]}
            db.add(JobRun(name=JOB, run_date=today, status="error", detail=result))
        db.commit()
        return result
    finally:
        db.close()


def _due() -> bool:
    now = datetime.now(TAIPEI)
    return now.weekday() < 5 and now.hour >= settings.DAILY_CHECK_HOUR


def _loop() -> None:
    while True:
        try:
            if _due():
                db = SessionLocal()
                errors_today = db.query(JobRun).filter(JobRun.name == JOB, JobRun.run_date == today_tw(),
                                                       JobRun.status == "error").count()
                db.close()
                if errors_today < 3:  # don't retry a broken run all night
                    run_once()
        except Exception as e:  # keep the scheduler alive
            print(f"daily_check scheduler error: {e}")
        time.sleep(15 * 60)


def start_scheduler() -> None:
    threading.Thread(target=_loop, daemon=True, name="daily-check").start()
