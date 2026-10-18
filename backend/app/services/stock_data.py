"""Turns raw FinMind rows into the shapes the overview and X-ray pages use.

Everything here is a pure transformation of real FinMind data - no estimates or
placeholders. Missing data stays None so the UI can say so instead of guessing.
"""
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.services.finmind import finmind_service

TICKER_RE = re.compile(r"^[0-9]{4,6}[A-Z]?$")

FOREIGN = {"Foreign_Investor", "Foreign_Dealer_Self"}
TRUST = {"Investment_Trust"}
DEALER = {"Dealer_self", "Dealer_Hedging"}


def pct_change(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None or old == 0:
        return None
    return (new - old) / abs(old) * 100


def find_stock(ticker: str) -> Optional[Dict[str, Any]]:
    rows = [r for r in finmind_service.stock_list() if r["stock_id"] == ticker]
    if not rows:
        return None
    industries = []
    for r in rows:
        if r["industry_category"] and r["industry_category"] not in industries:
            industries.append(r["industry_category"])
    return {
        "stock_id": ticker,
        "name": rows[0]["stock_name"],
        "industries": industries,
        "market": {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}.get(rows[0]["type"], rows[0]["type"]),
    }


def search_stocks(query: str, limit: int = 10) -> List[Dict[str, str]]:
    query = query.strip()
    if not query:
        return []
    seen, results = set(), []
    for r in finmind_service.stock_list():
        sid = r["stock_id"]
        if sid in seen or not TICKER_RE.match(sid):
            continue
        if sid.startswith(query) or query in r["stock_name"]:
            seen.add(sid)
            results.append({"stock_id": sid, "name": r["stock_name"]})
    # Exact code first, then shorter codes (common stocks before warrants/ETFs).
    results.sort(key=lambda s: (s["stock_id"] != query, len(s["stock_id"]), s["stock_id"]))
    return results[:limit]


def price_series(ticker: str) -> List[Dict[str, Any]]:
    rows = [r for r in finmind_service.prices(ticker) if r["close"] > 0]
    return [{
        "date": r["date"],
        "open": r["open"],
        "high": r["max"],
        "low": r["min"],
        "close": r["close"],
        "volume_lots": round(r["Trading_Volume"] / 1000),
    } for r in rows]


def institutional_series(ticker: str) -> List[Dict[str, Any]]:
    """Daily net buy per investor group, in lots (張, 1,000 shares)."""
    daily: Dict[str, Dict[str, float]] = defaultdict(lambda: {"foreign": 0.0, "trust": 0.0, "dealer": 0.0})
    for r in finmind_service.institutional(ticker):
        net = (r["buy"] - r["sell"]) / 1000
        if r["name"] in FOREIGN:
            daily[r["date"]]["foreign"] += net
        elif r["name"] in TRUST:
            daily[r["date"]]["trust"] += net
        elif r["name"] in DEALER:
            daily[r["date"]]["dealer"] += net
    out = []
    for d in sorted(daily):
        v = {k: round(x) for k, x in daily[d].items()}
        out.append({"date": d, **v, "total": v["foreign"] + v["trust"] + v["dealer"]})
    return out


def monthly_revenue(ticker: str) -> List[Dict[str, Any]]:
    """Monthly revenue keyed by the month it belongs to (not FinMind's publish date)."""
    by_month = {(r["revenue_year"], r["revenue_month"]): r["revenue"]
                for r in finmind_service.month_revenue(ticker)}
    out = []
    for (y, m) in sorted(by_month):
        rev = by_month[(y, m)]
        prev = by_month.get((y, m - 1) if m > 1 else (y - 1, 12))
        out.append({
            "period": f"{y}-{m:02d}",
            "year": y,
            "month": m,
            "revenue": rev,
            "yoy": pct_change(rev, by_month.get((y - 1, m))),
            "mom": pct_change(rev, prev),
        })
    return out


def revenue_summary(months: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not months:
        return None
    last = months[-1]
    ytd = [m for m in months if m["year"] == last["year"]]
    last_ytd = [m for m in months if m["year"] == last["year"] - 1 and m["month"] <= last["month"]]
    ytd_sum = sum(m["revenue"] for m in ytd)
    last_ytd_sum = sum(m["revenue"] for m in last_ytd) if len(last_ytd) == len(ytd) else None
    return {
        "period": last["period"],
        "revenue": last["revenue"],
        "yoy": last["yoy"],
        "mom": last["mom"],
        "ytd_revenue": ytd_sum,
        "ytd_yoy": pct_change(ytd_sum, last_ytd_sum),
    }


def quarterly_financials(ticker: str) -> List[Dict[str, Any]]:
    """Per-quarter income, cash flow and balance sheet items, oldest first.

    FinMind's income statement is already per quarter; its cash flow statement
    is year-to-date, so each quarter's cash flow is this YTD minus last quarter's YTD.
    """
    def pivot(rows, types):
        out: Dict[str, Dict[str, float]] = defaultdict(dict)
        for r in rows:
            if r["type"] in types:
                out[r["date"]][r["type"]] = r["value"]
        return out

    income = pivot(finmind_service.income_statement(ticker), {
        "Revenue", "GrossProfit", "OperatingIncome", "TotalNonoperatingIncomeAndExpense",
        "PreTaxIncome", "IncomeAfterTaxes", "EPS"})
    cash_ytd = pivot(finmind_service.cash_flow(ticker), {
        "CashFlowsFromOperatingActivities", "PropertyAndPlantAndEquipment"})
    balance = pivot(finmind_service.balance_sheet(ticker), {"AccountsReceivableNet", "Inventories"})

    def quarter_flow(d: str, key: str) -> Optional[float]:
        cur = cash_ytd.get(d, {}).get(key)
        if cur is None:
            return None
        if d.endswith("-03-31"):
            return cur
        prev_end = {"06-30": "03-31", "09-30": "06-30", "12-31": "09-30"}[d[5:]]
        prev = cash_ytd.get(f"{d[:4]}-{prev_end}", {}).get(key)
        return None if prev is None else cur - prev

    out = []
    for d in sorted(income):
        i = income[d]
        capex = quarter_flow(d, "PropertyAndPlantAndEquipment")
        out.append({
            "date": d,
            "quarter": f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}",
            "revenue": i.get("Revenue"),
            "gross_profit": i.get("GrossProfit"),
            "operating_income": i.get("OperatingIncome"),
            "non_operating": i.get("TotalNonoperatingIncomeAndExpense"),
            "pretax_income": i.get("PreTaxIncome"),
            "net_income": i.get("IncomeAfterTaxes"),
            "eps": i.get("EPS"),
            "operating_cash_flow": quarter_flow(d, "CashFlowsFromOperatingActivities"),
            "capex": -capex if capex is not None else None,
            "receivables": balance.get(d, {}).get("AccountsReceivableNet"),
            "inventories": balance.get(d, {}).get("Inventories"),
        })
    return out
