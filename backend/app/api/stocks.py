from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services import ai_report
from app.services.finmind import FinMindError
from app.services.stock_data import (
    TICKER_RE, find_stock, institutional_series, monthly_revenue, price_series,
    revenue_summary, search_stocks,
)
from app.services.xray import build_xray

router = APIRouter()


def _stock_or_404(ticker: str) -> dict:
    ticker = ticker.strip().upper()
    if not TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail="股票代碼格式不正確，請輸入 4-6 位數字，例如 2330。")
    try:
        stock = find_stock(ticker)
    except FinMindError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not stock:
        raise HTTPException(status_code=404, detail=f"查無股票代碼 {ticker}。")
    return stock


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=20)):
    try:
        return search_stocks(q)
    except FinMindError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{ticker}/overview")
def overview(ticker: str):
    stock = _stock_or_404(ticker)
    sid = stock["stock_id"]
    try:
        prices = price_series(sid)
        flows = institutional_series(sid)
        months = monthly_revenue(sid)
    except FinMindError as e:
        raise HTTPException(status_code=502, detail=str(e))

    latest = None
    if prices:
        last = prices[-1]
        prev = prices[-2]["close"] if len(prices) > 1 else None
        latest = {
            "date": last["date"],
            "close": last["close"],
            "change": None if prev is None else round(last["close"] - prev, 2),
            "change_pct": None if not prev else round((last["close"] - prev) / prev * 100, 2),
            "volume_lots": last["volume_lots"],
            "high_52w": max(p["high"] for p in prices[-250:]),
            "low_52w": min(p["low"] for p in prices[-250:]),
        }
    recent = flows[-20:]
    flow_sums = {
        f"{key}_{n}d": sum(f[key] for f in recent[-n:])
        for key in ("foreign", "trust", "dealer", "total") for n in (5, 20)
    }
    return {
        "stock": stock,
        "latest": latest,
        "prices": prices[-250:],
        "institutional": recent,
        "institutional_sums": flow_sums,
        "revenue_summary": revenue_summary(months),
        "monthly_revenue": months[-24:],
    }


@router.get("/{ticker}/xray")
def xray(ticker: str):
    stock = _stock_or_404(ticker)
    try:
        return {"stock": stock, **build_xray(stock["stock_id"])}
    except FinMindError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{ticker}/ai-report")
def get_ai_report(ticker: str, db: Session = Depends(get_db)):
    stock = _stock_or_404(ticker)
    return ai_report.serialize(ai_report.latest_report(db, stock["stock_id"]))


@router.post("/{ticker}/ai-report")
def create_ai_report(ticker: str, db: Session = Depends(get_db)):
    stock = _stock_or_404(ticker)
    return ai_report.serialize(ai_report.start_report(db, stock["stock_id"], stock["name"]))
