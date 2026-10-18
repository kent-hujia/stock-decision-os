from sqlalchemy.orm import Session
from app.models.schemas import Decision, DecisionStep, Thesis
from app.core.config import settings
from typing import List, Optional
import uuid

class DecisionService:
    def __init__(self, db: Session):
        self.db = db

    def create_decision(self, user_id: str, ticker: str) -> Decision:
        db_decision = Decision(
            id=uuid.uuid4(),
            user_id=user_id,
            ticker=ticker,
            status="Triage",
            conviction=5
        )
        self.db.add(db_decision)
        self.db.commit()
        self.db.refresh(db_decision)
        return db_decision

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        return self.db.query(Decision).filter(Decision.id == decision_id).first()

    def update_decision_status(self, decision_id: str, status: str, conviction: Optional[int] = None) -> Decision:
        db_decision = self.get_decision(decision_id)
        if not db_decision:
            return None

        db_decision.status = status
        if conviction is not None:
            db_decision.conviction = conviction

        self.db.commit()
        self.db.refresh(db_decision)
        return db_decision

    def add_step(self, decision_id: str, step_type: str, content: dict) -> DecisionStep:
        db_step = DecisionStep(
            id=uuid.uuid4(),
            decision_id=decision_id,
            step_type=step_type,
            content=content
        )
        self.db.add(db_step)
        self.db.commit()
        self.db.refresh(db_step)
        return db_step

    def get_decision_history(self, decision_id: str) -> List[DecisionStep]:
        return self.db.query(DecisionStep).filter(DecisionStep.decision_id == decision_id).all()

    def create_thesis(self, decision_id: str, hypothesis: str, metric: str, value: float) -> Thesis:
        db_thesis = Thesis(
            id=uuid.uuid4(),
            decision_id=decision_id,
            hypothesis=hypothesis,
            trigger_metric=metric,
            trigger_value=value
        )
        self.db.add(db_thesis)
        self.db.commit()
        self.db.refresh(db_thesis)
        return db_thesis
