import json
import anthropic
from app.core.config import settings

class AISkepticService:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate_questions(self, ticker: str, hypothesis: str) -> dict:
        """
        Generate 3 critical adversarial questions to challenge an investment thesis.
        """
        prompt = f"""
        You are a world-class Hedge Fund Short-Seller. Your goal is to destroy the following investment thesis and expose its flaws.
        Be brutal, logical, and data-driven. Do not be polite.

        Stock: {ticker}
        User's Thesis: {hypothesis}

        Task: Provide 3 critical questions that challenge the core assumptions of this thesis.
        Each question must target a different risk type:
        1. Fundamental Risk (e.g., revenue quality, moat erosion)
        2. Macro/Industry Risk (e.g., regulation, competitor shift)
        3. Valuation/Execution Risk (e.g., overpaying, management failure)

        Return ONLY a JSON object in the following format:
        {{
          "questions": [
            {{ "id": 1, "question": "...", "risk_type": "Fundamental" }},
            {{ "id": 2, "question": "...", "risk_type": "Macro" }},
            {{ "id": 3, "question": "...", "risk_type": "Valuation" }}
          ]
        }}
        """

        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(message.content[0].text)
        except Exception as e:
            print(f"AI Skeptic Error: {e}")
            # Fallback mock response
            return {
                "questions": [
                    {"id": 1, "question": "Is the growth sustainable or just a temporary spike?", "risk_type": "Fundamental"},
                    {"id": 2, "question": "What happens if the main competitor lowers prices by 20%?", "risk_type": "Macro"},
                    {"id": 3, "question": "Are you paying too much for a dream that might never happen?", "risk_type": "Valuation"}
                ]
            }

    def evaluate_rebuttal(self, question: str, rebuttal: str) -> dict:
        """
        Evaluate if the user's rebuttal successfully addresses the risk.
        """
        prompt = f"""
        As a critical short-seller, you asked the following question:
        "{question}"

        The investor responded:
        "{rebuttal}"

        Does this response effectively mitigate the risk? Or is it just a vague excuse?
        Rate the rebuttal: "Pass" or "Fail".
        Provide a short, biting reason for your decision.

        Return ONLY JSON:
        {{
          "status": "Pass" | "Fail",
          "reason": "..."
        }}
        """
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(message.content[0].text)
        except Exception as e:
            print(f"AI Evaluation Error: {e}")
            return {"status": "Fail", "reason": "Evaluation failed due to system error."}

ai_skeptic_service = AISkepticService()
