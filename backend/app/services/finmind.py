import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings


class FinMindError(Exception):
    """Raised when FinMind can't return data; the message is safe to show to users."""


class FinMindService:
    """Thin client for the FinMind v4 data API with an in-memory TTL cache.

    Each dataset+stock pair is fetched at most once per TTL, which keeps us well
    under FinMind's hourly quota (300 requests without a token, 600 with a free one).
    Transient FinMind failures are retried; if they persist and an older copy is
    cached, that copy is served (the pages show each dataset's as-of date).
    """

    BASE_URL = "https://api.finmindtrade.com/api/v4/data"
    RETRY_DELAYS = (1, 3)  # seconds before the 2nd and 3rd attempt

    def __init__(self):
        self.api_key = settings.FINMIND_API_KEY
        self._cache: Dict[tuple, tuple] = {}
        self._lock = threading.Lock()
        self._key_locks: Dict[tuple, threading.Lock] = {}

    def _fetch(self, params: Dict[str, str]) -> List[Dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        error: Optional[FinMindError] = None
        for delay in (0, *self.RETRY_DELAYS):
            time.sleep(delay)
            try:
                response = requests.get(self.BASE_URL, params=params, headers=headers, timeout=30)
                body = json.loads(response.text, strict=False)
            except (requests.RequestException, ValueError) as e:
                error = FinMindError(f"無法連線到 FinMind：{e}")
                continue
            if response.status_code == 402 or body.get("status") == 402:
                raise FinMindError("FinMind 本小時的查詢次數已用完，請稍後再試，或在後端設定 FINMIND_API_KEY 提高上限。")
            if response.status_code == 200 and body.get("status") == 200:
                return body.get("data", [])
            error = FinMindError(f"FinMind 回傳錯誤：{body.get('msg', response.status_code)}")
            if "level" in str(body.get("msg", "")).lower():
                break  # a paid-tier dataset won't succeed on retry
        raise error

    def _get(self, dataset: str, data_id: Optional[str] = None,
             start_date: Optional[str] = None, ttl: int = 3600) -> List[Dict[str, Any]]:
        key = (dataset, data_id, start_date)
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:  # parallel callers of the same dataset share one request
            with self._lock:
                hit = self._cache.get(key)
            if hit and time.time() - hit[0] < ttl:
                return hit[1]
            params = {"dataset": dataset}
            if data_id:
                params["data_id"] = data_id
            if start_date:
                params["start_date"] = start_date
            try:
                data = self._fetch(params)
            except FinMindError as e:
                if hit:
                    print(f"FinMind {dataset} {data_id} failed ({e}); serving cache from {time.ctime(hit[0])}")
                    return hit[1]
                raise
            with self._lock:
                self._cache[key] = (time.time(), data)
            return data

    def warm(self, ticker: str, *names: str) -> None:
        """Fetch several datasets for one stock in parallel so the sequential code that
        follows hits the cache. Failures are ignored here; the real call reports them."""
        def call(name):
            try:
                getattr(self, name)(ticker)
            except FinMindError:
                pass
        with ThreadPoolExecutor(max_workers=len(names) or 1) as pool:
            list(pool.map(call, names))

    @staticmethod
    def _since(days: int) -> str:
        # Round to the first of the month so the cache key stays stable all month.
        return (date.today() - timedelta(days=days)).replace(day=1).isoformat()

    def stock_list(self) -> List[Dict[str, Any]]:
        """All listed/OTC stocks with name and industry (one row per industry tag)."""
        return self._get("TaiwanStockInfo", ttl=24 * 3600)

    def prices(self, ticker: str, days: int = 400) -> List[Dict[str, Any]]:
        return self._get("TaiwanStockPrice", ticker, self._since(days), ttl=30 * 60)

    def institutional(self, ticker: str, days: int = 60) -> List[Dict[str, Any]]:
        return self._get("TaiwanStockInstitutionalInvestorsBuySell", ticker, self._since(days), ttl=30 * 60)

    def margin(self, ticker: str, days: int = 120) -> List[Dict[str, Any]]:
        """Margin purchase / short sale balances, in lots (張)."""
        return self._get("TaiwanStockMarginPurchaseShortSale", ticker, self._since(days), ttl=30 * 60)

    def short_balances(self, ticker: str, days: int = 120) -> List[Dict[str, Any]]:
        """Margin short and securities-lending (借券賣出) balances, in shares."""
        return self._get("TaiwanDailyShortSaleBalances", ticker, self._since(days), ttl=30 * 60)

    def shareholding(self, ticker: str, days: int = 120) -> List[Dict[str, Any]]:
        """Foreign investor shareholding ratio."""
        return self._get("TaiwanStockShareholding", ticker, self._since(days), ttl=30 * 60)

    def day_trading(self, ticker: str, days: int = 120) -> List[Dict[str, Any]]:
        """Day-trade volume, in shares."""
        return self._get("TaiwanStockDayTrading", ticker, self._since(days), ttl=30 * 60)

    def month_revenue(self, ticker: str, years: int = 4) -> List[Dict[str, Any]]:
        return self._get("TaiwanStockMonthRevenue", ticker, self._since(365 * years), ttl=6 * 3600)

    def income_statement(self, ticker: str, years: int = 4) -> List[Dict[str, Any]]:
        return self._get("TaiwanStockFinancialStatements", ticker, self._since(365 * years), ttl=6 * 3600)

    def cash_flow(self, ticker: str, years: int = 4) -> List[Dict[str, Any]]:
        return self._get("TaiwanStockCashFlowsStatement", ticker, self._since(365 * years), ttl=6 * 3600)

    def balance_sheet(self, ticker: str, years: int = 4) -> List[Dict[str, Any]]:
        return self._get("TaiwanStockBalanceSheet", ticker, self._since(365 * years), ttl=6 * 3600)


finmind_service = FinMindService()
