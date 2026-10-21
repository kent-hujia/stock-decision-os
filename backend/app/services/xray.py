"""Revenue quality X-ray: rule-based checks on real monthly and quarterly data.

Every check states the numbers it used, so a reader can verify the verdict
against the company's filings. Thresholds are deliberately simple and visible.
"""
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.finmind import finmind_service
from app.services.stock_data import monthly_revenue, pct_change, quarterly_financials, revenue_summary

XRAY_DATASETS = ("month_revenue", "income_statement", "cash_flow", "balance_sheet")

PENALTY = {"bad": 20, "warn": 8, "good": 0, "na": 0}


def _fmt_pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:+.1f}%"


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b * 100


def _check(cid: str, title: str, status: str, value: str, detail: str) -> Dict[str, str]:
    return {"id": cid, "title": title, "status": status, "value": value, "detail": detail}


def _na(cid: str, title: str, why: str) -> Dict[str, str]:
    return _check(cid, title, "na", "—", why)


def check_momentum(months: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "營收動能"
    yoys = [m["yoy"] for m in months if m["yoy"] is not None]
    if len(yoys) < 15:
        return _na("momentum", title, "月營收資料不足 15 個月，無法比較成長趨勢。")
    recent = mean(yoys[-3:])
    year = mean(yoys[-15:-3])
    detail = f"近 3 個月平均年增 {_fmt_pct(recent)}，之前 12 個月平均年增 {_fmt_pct(year)}。"
    if recent < -10:
        return _check("momentum", title, "bad", _fmt_pct(recent), detail + "營收明顯衰退。")
    if recent < 0 or recent < year - 15:
        return _check("momentum", title, "warn", _fmt_pct(recent), detail + "成長轉弱或明顯減速。")
    why = "由衰退轉為成長。" if year < 0 else "成長動能維持。"
    return _check("momentum", title, "good", _fmt_pct(recent), detail + why)


def check_low_base(months: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "低基期效應"
    by_period = {(m["year"], m["month"]): m for m in months}
    recent = months[-3:]
    if len(months) < 15 or not recent:
        return _na("low_base", title, "月營收資料不足，無法判斷去年基期。")
    hits = []
    for m in recent:
        last_year = by_period.get((m["year"] - 1, m["month"]))
        if m["yoy"] is not None and last_year and last_year["yoy"] is not None \
                and m["yoy"] > 20 and last_year["yoy"] < -10:
            hits.append(f"{m['period']} 年增 {_fmt_pct(m['yoy'])}，但去年同月本身年減 {_fmt_pct(last_year['yoy'])}")
    if hits:
        status = "bad" if len(hits) >= 2 else "warn"
        return _check("low_base", title, status, f"{len(hits)} 個月",
                      "；".join(hits) + "。高成長有一部分來自去年的低基期，不一定代表需求轉強。")
    return _check("low_base", title, "good", "未發現",
                  "近 3 個月的年增率沒有建立在去年大幅衰退的低基期上。")


def check_margin(quarters: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "毛利率趨勢"
    margins = [_ratio(q["gross_profit"], q["revenue"]) for q in quarters]
    if len(margins) < 5 or any(m is None for m in margins[-5:]):
        return _na("margin", title, "沒有毛利資料（金融業等不適用），或季資料不足 5 季。")
    latest, prior = margins[-1], mean(margins[-5:-1])
    diff = latest - prior
    detail = f"{quarters[-1]['quarter']} 毛利率 {latest:.1f}%，前 4 季平均 {prior:.1f}%（{diff:+.1f} 個百分點）。"
    if diff < -3:
        return _check("margin", title, "bad", f"{latest:.1f}%", detail + "毛利率明顯下滑，營收成長可能是靠降價或產品組合變差換來的。")
    if diff < -1:
        return _check("margin", title, "warn", f"{latest:.1f}%", detail + "毛利率小幅走弱。")
    return _check("margin", title, "good", f"{latest:.1f}%", detail + "毛利率持平或改善。")


def check_profit_vs_revenue(quarters: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "營收與本業獲利同步"
    if len(quarters) < 5:
        return _na("profit_sync", title, "季資料不足 5 季，無法計算年增。")
    cur, ago = quarters[-1], quarters[-5]
    rev_yoy = pct_change(cur["revenue"], ago["revenue"])
    op_yoy = pct_change(cur["operating_income"], ago["operating_income"])
    if rev_yoy is None or op_yoy is None:
        return _na("profit_sync", title, "缺少營收或營業利益資料。")
    detail = f"{cur['quarter']} 營收年增 {_fmt_pct(rev_yoy)}，營業利益年增 {_fmt_pct(op_yoy)}。"
    if rev_yoy > 0 and op_yoy < 0:
        return _check("profit_sync", title, "bad", "增收不增利", detail + "營收成長但本業獲利衰退。")
    if op_yoy < rev_yoy - 15:
        why = "本業獲利衰退幅度遠大於營收，成本或費用壓力上升。" if rev_yoy < 0 else "本業獲利成長明顯落後營收。"
        return _check("profit_sync", title, "warn", "獲利落後", detail + why)
    if rev_yoy < 0 and op_yoy < 0:
        return _check("profit_sync", title, "warn", "同步衰退", detail + "營收與本業獲利一起衰退。")
    return _check("profit_sync", title, "good", "同步", detail + "本業獲利跟上營收成長。")


def check_non_operating(quarters: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "業外收益占比"
    if not quarters:
        return _na("non_op", title, "沒有季報資料。")
    cur = quarters[-1]
    if cur["non_operating"] is None or not cur["pretax_income"] or cur["pretax_income"] <= 0:
        return _na("non_op", title, "稅前淨利為負或缺少業外資料，占比沒有意義。")
    share = cur["non_operating"] / cur["pretax_income"] * 100
    prior = [abs(q["non_operating"]) for q in quarters[-5:-1] if q["non_operating"] is not None]
    jump = prior and mean(prior) > 0 and cur["non_operating"] > 2 * mean(prior)
    detail = f"{cur['quarter']} 業外收支 {cur['non_operating'] / 1e8:,.1f} 億，占稅前淨利 {share:.1f}%。"
    if prior:
        detail += f"前 4 季業外平均 {mean(prior) / 1e8:,.1f} 億。"
    if share > 40:
        return _check("non_op", title, "bad", f"{share:.1f}%", detail + "獲利有很大一部分不是本業賺的。")
    if share > 20 or (jump and share > 10):
        why = "業外金額比過去暴增，可能是一次性收益（處分資產、匯兌、投資收益），要確認是否會延續。" if jump else "業外占比偏高。"
        return _check("non_op", title, "warn", f"{share:.1f}%", detail + why)
    return _check("non_op", title, "good", f"{share:.1f}%", detail + "獲利主要來自本業。")


def check_cash_conversion(quarters: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "獲利含金量（現金流）"
    last4 = quarters[-4:]
    if len(last4) < 4 or any(q["operating_cash_flow"] is None or q["net_income"] is None for q in last4):
        return _na("cash", title, "近 4 季現金流量資料不完整。")
    ocf = sum(q["operating_cash_flow"] for q in last4)
    ni = sum(q["net_income"] for q in last4)
    if ni <= 0:
        return _na("cash", title, f"近 4 季合計淨利為負（{ni / 1e8:,.1f} 億），比率沒有意義。")
    ratio = ocf / ni
    detail = f"近 4 季營業現金流 {ocf / 1e8:,.1f} 億，稅後淨利 {ni / 1e8:,.1f} 億，比率 {ratio:.2f} 倍。"
    if ratio < 0.5:
        return _check("cash", title, "bad", f"{ratio:.2f} 倍", detail + "帳上獲利大多沒有收到現金。")
    if ratio < 0.8:
        return _check("cash", title, "warn", f"{ratio:.2f} 倍", detail + "現金回收偏慢。")
    return _check("cash", title, "good", f"{ratio:.2f} 倍", detail + "獲利有實際現金流入支撐。")


def _check_balance_item(quarters, key: str, cid: str, title: str, label: str, why: str) -> Dict[str, str]:
    if len(quarters) < 5:
        return _na(cid, title, "季資料不足 5 季，無法計算年增。")
    cur, ago = quarters[-1], quarters[-5]
    item_yoy = pct_change(cur[key], ago[key])
    rev_yoy = pct_change(cur["revenue"], ago["revenue"])
    if item_yoy is None or rev_yoy is None:
        return _na(cid, title, f"缺少{label}資料（部分產業不適用）。")
    gap = item_yoy - rev_yoy
    detail = f"{cur['quarter']} {label}年增 {_fmt_pct(item_yoy)}，季營收年增 {_fmt_pct(rev_yoy)}。"
    if gap > 40:
        return _check(cid, title, "bad", f"差 {gap:.0f} 點", detail + why)
    if gap > 20:
        return _check(cid, title, "warn", f"差 {gap:.0f} 點", detail + why)
    return _check(cid, title, "good", "正常", detail + f"{label}與營收同步。")


def build_xray(ticker: str) -> Dict[str, Any]:
    finmind_service.warm(ticker, *XRAY_DATASETS)
    months = monthly_revenue(ticker)
    quarters = quarterly_financials(ticker)
    checks = [
        check_momentum(months),
        check_low_base(months),
        check_margin(quarters),
        check_profit_vs_revenue(quarters),
        check_non_operating(quarters),
        check_cash_conversion(quarters),
        _check_balance_item(quarters, "receivables", "receivables", "應收帳款", "應收帳款",
                            "應收帳款成長遠快於營收，可能放寬收款條件衝業績，或客戶付款變慢。"),
        _check_balance_item(quarters, "inventories", "inventory", "存貨水位", "存貨",
                            "存貨成長遠快於營收，可能有庫存堆積、未來跌價的風險。"),
    ]
    scored = [c for c in checks if c["status"] != "na"]
    score = None
    if len(scored) >= 4:
        score = max(0, 100 - sum(PENALTY[c["status"]] for c in scored))
    if score is None:
        grade = "資料不足"
    elif score >= 80:
        grade = "含金量高"
    elif score >= 60:
        grade = "大致健康"
    elif score >= 40:
        grade = "需要留意"
    else:
        grade = "高風險"
    return {
        "ticker": ticker,
        "score": score,
        "grade": grade,
        "checks": checks,
        "revenue_summary": revenue_summary(months),
        "monthly_revenue": months[-24:],
        "quarters": quarters[-12:],
        "data_as_of": {
            "month": months[-1]["period"] if months else None,
            "quarter": quarters[-1]["quarter"] if quarters else None,
        },
    }
