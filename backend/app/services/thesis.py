from app.services.ai_skeptic import ai_skeptic_service
from sqlalchemy.orm import Session
from app.models.schemas import Thesis
import uuid

class ThesisService:
    def __init__(self, db: Session):
        self.db = db

    def extract_theses_from_hypothesis(self, decision_id: str, hypothesis: str) -> List[Thesis]:
        """
        Use AI to extract concrete, monitorable hypotheses from a natural language thesis.
        Example: "Expect revenue growth > 10%" -> {metric: "revenue_yoy", value: 0.10}
        """
        prompt = f"""
        Extract all concrete, quantitative, and monitorable hypotheses from the following investment thesis.
        Thesis: {hypothesis}

        For each hypothesis, provide:
        1. The text of the hypothesis.
        2. The specific metric to monitor (e.g., 'revenue_yoy', 'institutional_flow', 'price_support').
        3. The threshold value that would trigger a 'Failure' of the hypothesis.

        Return ONLY a JSON array:
        [
          {{ "hypothesis": "...", "metric": "...", "value": 0.10 }}
        ]
        """
        try:
            import anthropic
            from app.core.config import settings
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-opus-5-5",
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}]
            )
            import json
            theses_data = json.loads(next(b.text for b in message.content if b.type == "text"))

            created_theses = []
            for data in theses_data:
                db_thesis = Thesis(
                    id=uuid.uuid4(),
                    decision_id=decision_id,
                    hypothesis=data['hypothesis'],
                    trigger_metric=data['metric'],
                    trigger_value=data['value']
                )
                self.db.add(db_thesis)
                created_theses.append(db_thesis)

            self.db.commit()
            return created_theses
        except Exception as e:
            print(f"Thesis Extraction Error: {e}")
            return []
