import numpy as np
from typing import List, Dict, Any, Optional
from app.services.finmind import finmind_service
from app.core.config import settings
import random # Used for simulating social data until scrapers are fully implemented

class SentimentService:
    def __init__(self):
        self.finmind = finmind_service

    def _calculate_z_score(self, current: float, history: List[float]) -> float:
        """Calculate Z-Score to measure deviation from historical mean."""
        if not history or len(history) < 2:
            return 0.0

        mean = np.mean(history)
        std = np.std(history)
        if std == 0:
            return 0.0

        return (current - mean) / std

    def get_retail_sentiment(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch social sentiment from PTT/Dcard/Threads.
        Note: In MVP, this simulates data. In Phase 2.1, it will use actual scrapers.
        """
        # Simulation logic for MVP
        # In production, this would call a scraper service
        return {
            "score": random.uniform(-1, 1),
            "volume": random.randint(100, 1000),
            "trend": random.choice(["up", "down", "flat"])
        }

    def get_institutional_sentiment(self, ticker: str) -> float:
        """
        Calculate institutional sentiment based on FinMind flow.
        Logic: Ratio of net buy/sell over the last 5-20 days.
        """
        flow_data = self.finmind.get_institutional_flow(ticker)
        if not flow_data:
            return 0.0

        # Assume flow_data is a list of daily records
        # Calculate the net flow of the last 10 days
        recent_flow = flow_data[-10:] if len(flow_data) >= 10 else flow_data
        net_flow = sum([float(day.get('net_buy', 0)) for day in recent_flow])

        # Normalize score between -1 and 1
        # This is a simplified normalization; in production we'd use a sliding window
        return max(-1.0, min(1.0, net_flow / 1000000)) # Scale by 1M shares for example

    def analyze_divergence(self, ticker: str) -> Dict[str, Any]:
        """
        Main analysis logic: Compare Retail vs Institutional.
        """
        retail = self.get_retail_sentiment(ticker)
        inst_score = self.get_institutional_sentiment(ticker)

        # Simulated historical data for Z-Score calculation
        # In production, this comes from the sentiment_logs table in PostgreSQL
        historical_retail = [random.uniform(-0.5, 0.5) for _ in range(30)]
        z_score = self._calculate_z_score(retail['score'], historical_retail)

        # Determine Divergence Status
        # Retail Down / Inst Up -> Professional Layout (Buy Signal)
        # Retail Up / Inst Down -> Retail Trap (Sell Signal)
        divergence = "Neutral"
        if retail['score'] < -0.2 and inst_score > 0.2:
            divergence = "Professional_Layout"
        elif retail['score'] > 0.2 and inst_score < -0.2:
            divergence = "Retail_Trap"

        return {
            "ticker": ticker,
            "retail_score": retail['score'],
            "inst_score": inst_score,
            "z_score": z_score,
            "divergence": divergence,
            "alert": self._get_alert_message(z_score, divergence)
        }

    def _get_alert_message(self, z_score: float, divergence: str) -> str:
        if abs(z_score) > 2.0:
            return "Extreme Sentiment: Market is overextended. Return to fundamentals."
        if divergence == "Retail_Trap":
            return "Danger: Retail crowd is euphoric while institutions are exiting."
        if divergence == "Professional_Layout":
            return "Opportunity: Quiet accumulation by institutions detected."
        return "Market sentiment is currently stable."

sentiment_service = SentimentService()
