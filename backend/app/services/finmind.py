import requests
from datetime import date, timedelta
from app.core.config import settings


class FinMindService:
    def __init__(self):
        self.api_key = settings.FINMIND_API_KEY
        self.base_url = "https://api.finmindtrade.com/api/v4/data"

    def _get(self, dataset: str, ticker: str, days: int):
        params = {
            "dataset": dataset,
            "data_id": ticker,
            "start_date": (date.today() - timedelta(days=days)).isoformat(),
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = requests.get(self.base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json().get("data", [])

    def get_stock_price(self, ticker: str):
        """Fetch the latest daily price row for a given ticker."""
        try:
            data = self._get("TaiwanStockPrice", ticker, 14)
            return data[-1] if data else None
        except Exception as e:
            print(f"Error fetching stock price for {ticker}: {e}")
            return None

    def get_institutional_flow(self, ticker: str):
        """Fetch institutional buy/sell, summed per day into {date, net_buy} records."""
        try:
            rows = self._get("TaiwanStockInstitutionalInvestorsBuySell", ticker, 45)
            daily = {}
            for row in rows:
                daily[row["date"]] = daily.get(row["date"], 0) + row["buy"] - row["sell"]
            return [{"date": d, "net_buy": daily[d]} for d in sorted(daily)]
        except Exception as e:
            print(f"Error fetching institutional flow for {ticker}: {e}")
            return None

    def get_financial_statements(self, ticker: str):
        """Fetch income statement rows (date, type, value) for revenue quality analysis."""
        try:
            return self._get("TaiwanStockFinancialStatements", ticker, 730)
        except Exception as e:
            print(f"Error fetching financial statements for {ticker}: {e}")
            return None


finmind_service = FinMindService()
