import requests
from app.core.config import settings

class FinMindService:
    def __init__(self):
        self.api_key = settings.FINMIND_API_KEY
        self.base_url = "https://api.finmindtrade.com/api/v4"

    def get_stock_price(self, ticker: str):
        """Fetch current stock price for a given ticker."""
        endpoint = f"{self.base_url}/stock-eod"
        params = {
            "stock_id": ticker,
            "api_key": self.api_key
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return data['data'][-1] if data['data'] else None
        except Exception as e:
            print(f"Error fetching stock price for {ticker}: {e}")
            return None

    def get_institutional_flow(self, ticker: str):
        """Fetch institutional buying/selling data."""
        endpoint = f"{self.base_url}/stock-institutional-trading"
        params = {
            "stock_id": ticker,
            "api_key": self.api_key
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return data['data']
        except Exception as e:
            print(f"Error fetching institutional flow for {ticker}: {e}")
            return None

    def get_financial_statements(self, ticker: str):
        """Fetch basic financial statements for revenue quality analysis."""
        endpoint = f"{self.base_url}/financial-statement"
        params = {
            "stock_id": ticker,
            "api_key": self.api_key
        }
        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return data['data']
        except Exception as e:
            print(f"Error fetching financial statements for {ticker}: {e}")
            return None

finmind_service = FinMindService()
