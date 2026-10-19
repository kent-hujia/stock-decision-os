"""Paper trading: virtual cash, real FinMind daily prices.

Fill rules (daily bars only, so intraday order is unknown - always assume the worse case):
- Orders placed on day D can only fill on bars dated after D.
- Market order: fills at the next bar's open. Limit buy: fills at the open if it opens at or
  below the limit, otherwise at the limit if the bar's low reaches it.
- Unfilled orders are cancelled after `expire_days` bars.
- On the fill day only the stop is checked. Afterwards, if a bar touches both stop and target,
  the stop wins. Gaps fill at the open.
- Costs: 0.1425% commission each side (min NT$20), 0.3% securities transaction tax on sells.
"""
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

from app.models.schemas import PaperAccount, PaperTrade, PaperTradeEvent
from app.services.ai_report import today_tw
from app.services.stock_data import price_series

FEE_RATE = 0.001425
MIN_FEE = 20
TAX_RATE = 0.003

MISTAKES = {
    "chase": "追高進場",
    "no_signal": "沒等到訊號就進場",
    "against_trend": "逆勢交易",
    "ignored_chips": "忽略籌碼警訊",
    "stop_too_tight": "停損設太近",
    "stop_too_wide": "停損設太遠",
    "target_too_greedy": "目標價太貪心",
    "early_exit": "太早獲利了結",
    "moved_stop_down": "把停損往下移",
    "oversized": "部位太大",
}


def fee(amount: float) -> float:
    return float(max(MIN_FEE, round(amount * FEE_RATE)))


def tax(amount: float) -> float:
    return float(round(amount * TAX_RATE))


def get_account(db) -> PaperAccount:
    account = db.get(PaperAccount, 1)
    if account is None:
        account = PaperAccount(id=1)
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def event(db, trade: PaperTrade, event_type: str, content: Optional[dict] = None,
          bar_date: Optional[str] = None) -> PaperTradeEvent:
    e = PaperTradeEvent(trade_id=trade.id, event_type=event_type, content=content or {}, bar_date=bar_date)
    db.add(e)
    return e


def cash(db, account: PaperAccount, exclude_id: Optional[int] = None) -> float:
    """Cash after every fill so far."""
    total = account.initial_cash
    for t in db.query(PaperTrade).filter(PaperTrade.status.in_(("open", "closed"))):
        if t.id == exclude_id:
            continue
        total -= t.entry_price * t.shares + t.entry_fee
        if t.status == "closed":
            total += t.exit_price * t.shares - t.exit_fee - t.exit_tax
    return total


def order_price(t: PaperTrade) -> float:
    return t.limit_price if t.order_type == "limit" else t.ref_price


def reserved(db, exclude_id: Optional[int] = None) -> float:
    """Cash set aside for unfilled orders (with 3% headroom for a gap up and the fee)."""
    return sum(order_price(t) * t.shares * 1.03 for t in db.query(PaperTrade).filter(PaperTrade.status == "planned")
               if t.id != exclude_id)


def pnl(t: PaperTrade) -> Optional[float]:
    if t.status != "closed":
        return None
    return t.exit_price * t.shares - t.exit_fee - t.exit_tax - (t.entry_price * t.shares + t.entry_fee)


def r_multiple(t: PaperTrade) -> Optional[float]:
    """Result in units of the initial risk (entry - initial stop), after costs."""
    if t.status != "closed" or t.entry_price <= t.initial_stop:
        return None
    return pnl(t) / ((t.entry_price - t.initial_stop) * t.shares)


# --- Simulation ------------------------------------------------------------------------

def _close(db, t: PaperTrade, bar: Dict[str, Any], price: float, reason: str, gap: bool = False) -> None:
    amount = price * t.shares
    t.status, t.exit_date, t.exit_price, t.exit_reason = "closed", bar["date"], price, reason
    t.exit_fee, t.exit_tax = fee(amount), tax(amount)
    event(db, t, "closed", {"reason": reason, "price": price, "gap": gap, "pnl": pnl(t),
                            "r": r_multiple(t)}, bar["date"])


def _check_exit(db, t: PaperTrade, bar: Dict[str, Any], fill_day: bool) -> bool:
    t.high_since_entry = max(t.high_since_entry or bar["high"], bar["high"])
    t.low_since_entry = min(t.low_since_entry or bar["low"], bar["low"])
    if not fill_day and t.exit_requested_date and bar["date"] > t.exit_requested_date:
        _close(db, t, bar, bar["open"], "manual")
    elif not fill_day and bar["open"] <= t.stop_price:
        _close(db, t, bar, bar["open"], "stop", gap=True)
    elif bar["low"] <= t.stop_price:
        _close(db, t, bar, t.stop_price, "stop")
    elif fill_day:
        return False
    elif bar["open"] >= t.target_price:
        _close(db, t, bar, bar["open"], "target", gap=True)
    elif bar["high"] >= t.target_price:
        _close(db, t, bar, t.target_price, "target")
    return t.status == "closed"


def _try_fill(db, account: PaperAccount, t: PaperTrade, bar: Dict[str, Any]) -> bool:
    if t.order_type == "market":
        price = bar["open"]
    elif bar["open"] <= t.limit_price:
        price = bar["open"]
    elif bar["low"] <= t.limit_price:
        price = t.limit_price
    else:
        return False
    cost = price * t.shares
    if cost + fee(cost) > cash(db, account) - reserved(db, exclude_id=t.id):
        t.status, t.cancel_reason = "cancelled", "insufficient_cash"
        event(db, t, "cancelled", {"reason": "資金不足，無法以開盤價成交", "price": price}, bar["date"])
        return False
    t.status, t.entry_date, t.entry_price, t.entry_fee = "open", bar["date"], price, fee(cost)
    event(db, t, "filled", {"price": price, "shares": t.shares, "fee": t.entry_fee,
                            "order_type": t.order_type}, bar["date"])
    return True


def sync_trade(db, account: PaperAccount, t: PaperTrade, bars: Optional[List[Dict[str, Any]]] = None) -> None:
    """Process every bar after the last one seen. Safe to call repeatedly."""
    if t.status not in ("planned", "open"):
        return
    bars = bars if bars is not None else price_series(t.ticker)
    start = t.last_synced_date or t.plan_date
    for bar in [b for b in bars if b["date"] > start]:
        if t.status == "planned":
            waited = sum(1 for b in bars if t.plan_date < b["date"] < bar["date"])
            if waited >= t.expire_days:
                t.status, t.cancel_reason = "cancelled", "expired"
                event(db, t, "cancelled", {"reason": f"{t.expire_days} 個交易日內沒有成交，委託失效"}, bar["date"])
            elif _try_fill(db, account, t, bar):
                _check_exit(db, t, bar, fill_day=True)
        elif t.status == "open":
            _check_exit(db, t, bar, fill_day=False)
        t.last_synced_date = bar["date"]
        if t.status not in ("planned", "open"):
            break


def sync_all(db) -> List[PaperTrade]:
    """Bring every active trade up to date; returns the trades that were active."""
    account = get_account(db)
    active = db.query(PaperTrade).filter(PaperTrade.status.in_(("planned", "open"))).order_by(PaperTrade.id).all()
    bars_by_ticker: Dict[str, List[Dict[str, Any]]] = {}
    for t in active:
        if t.ticker not in bars_by_ticker:
            bars_by_ticker[t.ticker] = price_series(t.ticker)
        sync_trade(db, account, t, bars_by_ticker[t.ticker])
        db.flush()  # later fills see this one's cash
    db.commit()
    return active


# --- Summaries -----------------------------------------------------------------------------

def last_close(ticker: str) -> Optional[Dict[str, Any]]:
    bars = price_series(ticker)
    return bars[-1] if bars else None


def account_summary(db) -> Dict[str, Any]:
    account = get_account(db)
    open_trades = db.query(PaperTrade).filter(PaperTrade.status == "open").all()
    market_value = 0.0
    for t in open_trades:
        bar = last_close(t.ticker)
        market_value += (bar["close"] if bar else t.entry_price) * t.shares
    c = cash(db, account)
    equity = c + market_value
    return {
        "initial_cash": account.initial_cash, "risk_pct": account.risk_pct,
        "cash": round(c), "reserved": round(reserved(db)), "available": round(c - reserved(db)),
        "market_value": round(market_value), "equity": round(equity),
        "return_pct": round((equity / account.initial_cash - 1) * 100, 2),
        "risk_budget": round(equity * account.risk_pct / 100),
    }


def stats(db) -> Dict[str, Any]:
    closed = (db.query(PaperTrade).filter(PaperTrade.status == "closed")
              .order_by(PaperTrade.exit_date, PaperTrade.id).all())
    account = get_account(db)
    rs = [r for r in (r_multiple(t) for t in closed) if r is not None]
    pnls = [pnl(t) for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    equity, peak, max_dd, curve = account.initial_cash, account.initial_cash, 0.0, []
    for t, p in zip(closed, pnls):
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100)
        curve.append({"date": t.exit_date, "equity": round(equity), "trade_id": t.id})
    by_mistake: Dict[str, Dict[str, Any]] = {}
    for t, p in zip(closed, pnls):
        for m in t.mistakes or []:
            row = by_mistake.setdefault(m, {"key": m, "label": MISTAKES.get(m, m), "count": 0, "pnl": 0.0, "r": 0.0})
            row["count"] += 1
            row["pnl"] += p
            row["r"] += r_multiple(t) or 0
    reviewed = [t for t in closed if t.reviewed_at]
    return {
        "closed": len(closed),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_r": round(mean(rs), 2) if rs else None,
        "avg_win": round(mean(wins)) if wins else None,
        "avg_loss": round(mean(losses)) if losses else None,
        "profit_factor": round(sum(wins) / -sum(losses), 2) if wins and losses and sum(losses) < 0 else None,
        "realized_pnl": round(sum(pnls)),
        "max_drawdown_pct": round(max_dd, 2),
        "followed_plan_pct": round(sum(1 for t in reviewed if t.followed_plan) / len(reviewed) * 100, 1) if reviewed else None,
        "unreviewed": len(closed) - len(reviewed),
        "equity_curve": curve,
        "mistakes": sorted(by_mistake.values(), key=lambda r: r["pnl"]),
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def plan_date_now() -> str:
    return today_tw()
