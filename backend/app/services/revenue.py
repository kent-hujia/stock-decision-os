from app.services.llm_json import parse_llm_json
import json
import anthropic
from typing import Dict, Any, List
from app.core.config import settings
from app.services.mops import mops_service
from app.services.finmind import finmind_service

class RevenueAnalysisService:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.mops = mops_service
        self.finmind = finmind_service

    def analyze_revenue_quality(self, ticker: str) -> Dict[str, Any]:
        """
        Complete Revenue X-Ray process:
        Data Fetching -> AI Decomposition -> Trap Detection -> Score Calculation.
        """
        # 1. Fetch Data
        mda_text = self.mops.fetch_mda_text(ticker)
        financials = self.finmind.get_financial_statements(ticker)

        if not mda_text:
            return {"error": "Could not fetch MD&A text from MOPS"}

        # 2. AI Decomposition (The Storyline)
        storyline = self._decompose_storyline(ticker, mda_text)

        # 3. Trap Detection
        traps = self._detect_revenue_traps(ticker, financials)

        # 4. Calculate Final Quality Score
        # Logic: Base score 100, deduct for Red paths, add for Green, deduct for traps.
        quality_score = self._calculate_quality_score(storyline, traps)

        return {
            "ticker": ticker,
            "quality_score": quality_score,
            "storyline": storyline,
            "traps": traps,
            "conclusion": self._generate_conclusion(quality_score, traps)
        }

    def _decompose_storyline(self, ticker: str, text: str) -> List[Dict[str, Any]]:
        """Use AI to break down revenue into Green/Red/Yellow paths."""
        prompt = f"""
        You are a Forensic Accountant specializing in the Taiwan Stock Market.
        Analyze the following MD&A text for stock {ticker} and decompose the revenue growth into a storyline.

        Text: {text}

        Categorize each growth driver into:
        - Green (High Quality): Organic growth, new product success, market share gain.
        - Red (Low Quality): One-time asset sale, exchange gain, accounting adjustments.
        - Yellow (Mixed): Subsidiary contributions, M&A growth, price hikes without volume growth.

        Return ONLY a JSON array of paths:
        [
          {{ "type": "green", "amount": "description of amount", "evidence": "quote from text" }},
          {{ "type": "red", "amount": "...", "evidence": "..." }}
        ]
        """
        try:
            message = self.client.messages.create(
                model="claude-opus-5-5",
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}]
            )
            return parse_llm_json(message)
        except Exception as e:
            print(f"Decomposition Error: {e}")
            return [{"type": "unknown", "amount": "Error", "evidence": "Failed to analyze"}]

    def _detect_revenue_traps(self, ticker: str, financials: List[Dict]) -> List[Dict]:
        """Detect common Taiwan stock revenue traps."""
        traps = []
        if not financials:
            return traps

        # Example Logic: Base Effect Check (Simulated)
        # Real logic would compare current YoY with historical average
        # if current_yoy > 2 * avg_yoy: traps.append({"type": "LowBase", "desc": " la-base effect detected"})

        # Example Logic: Revenue vs Cash flow divergence
        # if rev_growth > 20% and cash_flow_growth < 0: traps.append({"type": "CashDivergence", "desc": "Revenue grew but cash didn't"})

        # Mock traps for MVP visualization
        if ticker == "2330":
            traps.append({"type": "CurrencyEffect", "desc": "Significant portion of growth driven by USD/TWD exchange rate."})
        elif ticker == "2454":
            traps.append({"type": "InternalTrading", "desc": "High proportion of internal transactions with subsidiaries."})

        return traps

    def _calculate_quality_score(self, storyline: List[Dict], traps: List[Dict]) -> float:
        score = 80.0 # Base score
        for path in storyline:
            if path['type'] == 'green': score += 10
            if path['type'] == 'red': score -= 20
            if path['type'] == 'yellow': score -= 5

        score -= (len(traps) * 15)
        return max(0.0, min(100.0, score))

    def _generate_conclusion(self, score: float, traps: List[Dict]) -> str:
        if score > 80: return "High Quality: Durable organic growth detected."
        if score > 60: return "Moderate Quality: Growth is healthy but contains some noise."
        if score > 40: return "Low Quality: Growth is largely artificial or risky."
        return "Danger: Highly artificial growth, potential bubble."

revenue_analysis_service = RevenueAnalysisService()
