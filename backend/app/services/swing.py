"""Swing-trade checklist: trend, volume, chips and a technical stop level, all from real FinMind data.

Like the revenue X-ray, every check states the numbers it used and its
thresholds are simple and visible. There is no overall score: the checklist
is there to make the trader look at each item, not to say buy or sell.
"""
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.stock_data import chip_series, institutional_series, pct_change, price_series
from app.services.finmind import finmind_service
from app.services.xray import XRAY_DATASETS, _check, _fmt_pct, _na, build_xray

SWING_DATASETS = ("prices", "institutional", "margin", "short_balances", "shareholding", "day_trading")


def tick_size(price: float) -> float:
    """TWSE/TPEx price tick for a stock at this price."""
    for limit, tick in ((10, 0.01), (50, 0.05), (100, 0.1), (500, 0.5), (1000, 1)):
        if price < limit:
            return tick
    return 5


def round_down_tick(price: float) -> float:
    tick = tick_size(price)
    return round(int(price / tick + 1e-9) * tick, 2)


def round_up_tick(price: float) -> float:
    tick = tick_size(price)
    return round(-int(-price / tick + 1e-9) * tick, 2)


def moving_average(values: List[float], n: int, end: Optional[int] = None) -> Optional[float]:
    """Average of the n values ending at index `end` (exclusive), or the last n."""
    end = len(values) if end is None else end
    if end < n:
        return None
    return mean(values[end - n:end])


def _streak(values: List[float]) -> int:
    """Consecutive days of buying (+) or selling (-) at the end of the series."""
    streak = 0
    for v in reversed(values):
        if v == 0 or (streak > 0 and v < 0) or (streak < 0 and v > 0):
            break
        streak += 1 if v > 0 else -1
    return streak


def _streak_text(streak: int) -> str:
    if streak > 0:
        return f"連續買超 {streak} 天"
    if streak < 0:
        return f"連續賣超 {-streak} 天"
    return "最近一天持平"


def check_trend(prices: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "趨勢（均線）"
    closes = [p["close"] for p in prices]
    if len(closes) < 65:
        return _na("trend", title, "股價資料不足 65 個交易日，無法計算 60 日均線。")
    close, ma20, ma60 = closes[-1], moving_average(closes, 20), moving_average(closes, 60)
    ma20_prev = moving_average(closes, 20, len(closes) - 5)
    bias = (close / ma20 - 1) * 100
    slope = "上揚" if ma20 > ma20_prev else "下彎"
    detail = (f"{prices[-1]['date']} 收盤 {close:g}，20 日均線 {ma20:.1f}（較 5 日前{slope}），"
              f"60 日均線 {ma60:.1f}；股價距 20 日均線 {bias:+.1f}%。")
    if close > ma20 > ma60 and ma20 > ma20_prev:
        if bias > 10:
            return _check("trend", title, "warn", "多頭但乖離大", detail + "趨勢向上，但股價離均線太遠，追高容易買在短線高點。")
        return _check("trend", title, "good", "多頭排列", detail + "股價、20 日、60 日均線由上而下排列，短中期趨勢向上。")
    if close < ma20 < ma60 and ma20 < ma20_prev:
        return _check("trend", title, "bad", "空頭排列", detail + "股價在兩條均線之下且均線下彎，逆勢做多風險高。")
    return _check("trend", title, "warn", "整理中", detail + "均線沒有明確方向，趨勢還在整理。")


def check_volume(prices: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "量能"
    if len(prices) < 25:
        return _na("volume", title, "股價資料不足 25 個交易日。")
    vols = [p["volume_lots"] for p in prices]
    avg5, avg20 = moving_average(vols, 5), moving_average(vols, 20)
    if not avg20:
        return _na("volume", title, "近 20 日沒有成交量。")
    ratio = avg5 / avg20
    move = pct_change(prices[-1]["close"], prices[-6]["close"])
    detail = (f"近 5 日均量 {avg5:,.0f} 張，20 日均量 {avg20:,.0f} 張（{ratio:.2f} 倍）；"
              f"5 日股價 {_fmt_pct(move)}。")
    if ratio >= 1.3 and move is not None and move > 0:
        return _check("volume", title, "good", "價漲量增", detail + "上漲有成交量支撐。")
    if ratio >= 1.3:
        return _check("volume", title, "bad", "價跌量增", detail + "下跌時成交量放大，可能有人在出貨。")
    if ratio < 0.7:
        return _check("volume", title, "warn", "量縮", detail + "成交量明顯萎縮，市場觀望；若是拉回時量縮，賣壓不大。")
    if move is not None and move < 0:
        return _check("volume", title, "warn", "量平價跌", detail + "量能平穩但股價走弱。")
    return _check("volume", title, "good", "量能平穩", detail + "量價沒有異常。")


def check_institutional(flows: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "法人動向（外資・投信）"
    recent = flows[-20:]
    if len(recent) < 10:
        return _na("institutional", title, "法人買賣超資料不足 10 個交易日。")
    f20, t20 = sum(f["foreign"] for f in recent), sum(f["trust"] for f in recent)
    fs, ts = _streak([f["foreign"] for f in recent]), _streak([f["trust"] for f in recent])
    detail = (f"近 {len(recent)} 日外資 {f20:+,} 張（{_streak_text(fs)}），"
              f"投信 {t20:+,} 張（{_streak_text(ts)}）。")
    if f20 > 0 and t20 > 0:
        return _check("institutional", title, "good", "同步買超", detail + "外資與投信同方向買進。")
    if f20 < 0 and t20 < 0:
        return _check("institutional", title, "bad", "同步賣超", detail + "外資與投信都在賣，波段做多缺乏法人支撐。")
    if fs >= 3 or ts >= 3:
        return _check("institutional", title, "warn", "轉買中", detail + "法人方向不一致，但最近有一方連續買進，留意是否延續。")
    return _check("institutional", title, "warn", "方向分歧", detail + "外資與投信方向不一致。")


def check_margin(chips: List[Dict[str, Any]], prices: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "融資（散戶籌碼）"
    if len(chips) < 21 or not chips[-21]["margin_balance"]:
        return _na("margin", title, "融資資料不足 20 個交易日，或這檔股票不能融資。")
    cur, ago = chips[-1]["margin_balance"], chips[-21]["margin_balance"]
    chg = pct_change(cur, ago)
    price_by_date = {p["date"]: p["close"] for p in prices}
    price_chg = pct_change(price_by_date.get(chips[-1]["date"]), price_by_date.get(chips[-21]["date"]))
    short = chips[-1]["short_balance"]
    ratio = short / cur * 100 if cur else None
    detail = (f"融資餘額 {cur:,} 張，20 日 {_fmt_pct(chg)}（{ago:,} → {cur:,}）；同期股價 {_fmt_pct(price_chg)}。"
              f"融券 {short:,} 張" + (f"，券資比 {ratio:.1f}%。" if ratio is not None else "。"))
    if chg > 10 and price_chg is not None and price_chg < 0:
        return _check("margin", title, "bad", "融資增・股價跌", detail + "散戶用融資接刀，籌碼變亂，下跌時容易出現斷頭賣壓。")
    if chg > 15:
        return _check("margin", title, "warn", "融資暴增", detail + "散戶大量追價，籌碼集中在不穩定的人手上。")
    if chg < 0 and price_chg is not None and price_chg > 0:
        return _check("margin", title, "good", "融資減・股價漲", detail + "散戶退場而股價上漲，籌碼往法人或大戶集中。")
    return _check("margin", title, "good", "變化溫和", detail + "融資沒有異常增減。")


def check_short(chips: List[Dict[str, Any]], prices: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "空方（借券賣出）"
    rows = [c for c in chips if c["sbl_balance"] is not None]
    if len(rows) < 21:
        return _na("short", title, "借券賣出餘額資料不足 20 個交易日。")
    cur, ago = rows[-1]["sbl_balance"], rows[-21]["sbl_balance"]
    chg = cur - ago
    avg_vol = moving_average([p["volume_lots"] for p in prices], 20) or 0
    days = chg / avg_vol if avg_vol else 0
    detail = f"借券賣出餘額 {cur:,} 張，20 日 {chg:+,} 張（約 {days:.1f} 天的平均成交量）。"
    if days > 3:
        return _check("short", title, "bad", "空方大增", detail + "法人透過借券大量放空，上漲時賣壓可能很重。")
    if days > 1:
        return _check("short", title, "warn", "空方增加", detail + "借券放空增加，留意法人是否看空或在避險。")
    if chg < 0:
        return _check("short", title, "good", "空方回補", detail + "借券賣出餘額下降，空方在回補。")
    return _check("short", title, "good", "變化不大", detail + "借券放空沒有明顯增加。")


def check_foreign_holding(chips: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "外資持股比率"
    rows = [c for c in chips if c["foreign_ratio"] is not None]
    if len(rows) < 21:
        return _na("foreign_holding", title, "外資持股資料不足 20 個交易日。")
    cur, ago = rows[-1]["foreign_ratio"], rows[-21]["foreign_ratio"]
    diff = cur - ago
    detail = f"外資持股 {cur:.2f}%，20 日前 {ago:.2f}%（{diff:+.2f} 個百分點）。"
    if diff >= 0.2:
        return _check("foreign_holding", title, "good", f"{diff:+.2f} 點", detail + "外資持續加碼。")
    if diff <= -1:
        return _check("foreign_holding", title, "bad", f"{diff:+.2f} 點", detail + "外資明顯撤出。")
    if diff <= -0.2:
        return _check("foreign_holding", title, "warn", f"{diff:+.2f} 點", detail + "外資小幅減碼。")
    return _check("foreign_holding", title, "good", f"{diff:+.2f} 點", detail + "外資持股穩定。")


def check_day_trade(chips: List[Dict[str, Any]]) -> Dict[str, str]:
    title = "當沖比"
    ratios = [c["day_trade_ratio"] for c in chips[-5:] if c["day_trade_ratio"] is not None]
    if len(ratios) < 3:
        return _na("day_trade", title, "當沖資料不足。")
    avg = mean(ratios)
    detail = f"近 {len(ratios)} 日當沖成交占總成交量平均 {avg:.1f}%。"
    if avg > 40:
        return _check("day_trade", title, "bad", f"{avg:.1f}%", detail + "當沖客主導，股價波動大、容易暴漲暴跌，波段持有不穩。")
    if avg > 25:
        return _check("day_trade", title, "warn", f"{avg:.1f}%", detail + "短線投機比例偏高。")
    return _check("day_trade", title, "good", f"{avg:.1f}%", detail + "以非當沖的持有者為主。")


def check_revenue_quality(ticker: str) -> Dict[str, str]:
    title = "營收品質（X 光）"
    xray = build_xray(ticker)
    score = xray["score"]
    if score is None:
        return _na("revenue", title, "營收 X 光資料不足，無法評分（金融業等不適用）。")
    bad = [c["title"] for c in xray["checks"] if c["status"] == "bad"]
    detail = f"營收 X 光 {score} 分（{xray['grade']}）" + (f"，警訊：{'、'.join(bad)}。" if bad else "，沒有警訊。")
    if score >= 60:
        return _check("revenue", title, "good", f"{score} 分", detail + "基本面沒有明顯虛胖。")
    if score >= 40:
        return _check("revenue", title, "warn", f"{score} 分", detail + "基本面有疑點，波段操作要嚴守停損。")
    return _check("revenue", title, "bad", f"{score} 分", detail + "營收品質差，題材退燒時容易急跌。")


def defense_levels(prices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Suggested stop and reference targets from recent lows, highs and moving averages."""
    if len(prices) < 25:
        return None
    closes = [p["close"] for p in prices]
    close = closes[-1]
    ma20, ma60 = moving_average(closes, 20), moving_average(closes, 60)
    low10 = min(p["low"] for p in prices[-10:])
    low20 = min(p["low"] for p in prices[-20:])
    low60 = min(p["low"] for p in prices[-60:])
    high20 = max(p["high"] for p in prices[-20:])
    high60 = max(p["high"] for p in prices[-60:])
    # The nearest support at least 2% below the close; anything closer is daily noise.
    candidates = [(v, label) for v, label in ((low10, "近 10 日低點"), (low20, "近 20 日低點"), (low60, "近 60 日低點"),
                                              (ma20, "20 日均線"), (ma60, "60 日均線"))
                  if v is not None and v <= close * 0.98]
    if candidates:
        level, basis = max(candidates)
        stop = round_down_tick(level - tick_size(level))
    else:
        stop = round_down_tick(close * 0.93)
        basis = "收盤價下方 2% 以外沒有明確支撐，暫以收盤價 -7% 計"
    risk = close - stop
    return {
        "date": prices[-1]["date"], "close": close,
        "ma20": None if ma20 is None else round(ma20, 2), "ma60": None if ma60 is None else round(ma60, 2),
        "low10": low10, "low20": low20, "low60": low60, "high20": high20, "high60": high60,
        "suggested_stop": stop, "stop_basis": basis,
        "stop_distance_pct": round(risk / close * 100, 2),
        "suggested_target": round_up_tick(close + 2 * risk),
    }


def build_swing(ticker: str) -> Dict[str, Any]:
    finmind_service.warm(ticker, *SWING_DATASETS, *XRAY_DATASETS)
    prices = price_series(ticker)
    flows = institutional_series(ticker)
    chips = chip_series(ticker)
    checks = [
        check_trend(prices),
        check_volume(prices),
        check_institutional(flows),
        check_margin(chips, prices),
        check_short(chips, prices),
        check_foreign_holding(chips),
        check_day_trade(chips),
        check_revenue_quality(ticker),
    ]
    closes = [p["close"] for p in prices]
    chart = []
    for i in range(max(0, len(prices) - 120), len(prices)):
        ma20, ma60 = moving_average(closes, 20, i + 1), moving_average(closes, 60, i + 1)
        chart.append({**prices[i], "ma20": None if ma20 is None else round(ma20, 2),
                      "ma60": None if ma60 is None else round(ma60, 2)})
    return {
        "ticker": ticker,
        "checks": checks,
        "defense": defense_levels(prices),
        "prices": chart,
        "chips": chips[-60:],
        "institutional": flows[-20:],
        "data_as_of": {"price": prices[-1]["date"] if prices else None,
                       "chips": chips[-1]["date"] if chips else None},
    }
