from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.services.decision import DecisionService
from app.services.ai_skeptic import ai_skeptic_service
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()

# Pydantic models for request/response
class DecisionCreate(BaseModel):
    user_id: str
    ticker: str

class StepCreate(BaseModel):
    step_type: str
    content: dict

class StatusUpdate(BaseModel):
    status: str
    conviction: Optional[int] = None

class RebuttalCreate(BaseModel):
    question_id: int
    rebuttal: str

@router.post("/start")
async def start_decision(payload: DecisionCreate, db: Session = Depends(get_db)):
    service = DecisionService(db)
    return service.create_decision(payload.user_id, payload.ticker)

@router.get("/{decision_id}")
async def get_decision(decision_id: str, db: Session = Depends(get_db)):
    service = DecisionService(db)
    decision = service.get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision

@router.post("/{decision_id}/step")
async def add_step(decision_id: str, payload: StepCreate, db: Session = Depends(get_db)):
    service = DecisionService(db)
    return service.add_step(decision_id, payload.step_type, payload.content)

@router.patch("/{decision_id}/status")
async def update_status(decision_id: str, payload: StatusUpdate, db: Session = Depends(get_db)):
    service = DecisionService(db)
    decision = service.update_decision_status(decision_id, payload.status, payload.conviction)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision

@router.get("/{decision_id}/history")
async def get_history(decision_id: str, db: Session = Depends(get_db)):
    service = DecisionService(db)
    return service.get_decision_history(decision_id)

@router.post("/{decision_id}/adversarial/questions")
async def generate_skeptic_questions(decision_id: str, hypothesis: str, db: Session = Depends(get_db)):
    """
    Triggers AI to generate adversarial questions based on the hypothesis.
    """
    decision = DecisionService(db).get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    questions = ai_skeptic_service.generate_questions(decision.ticker, hypothesis)
    # Store the questions as a step
    DecisionService(db).add_step(decision_id, "Skeptic_Questions", {"questions": questions})

    return questions

@router.post("/{decision_id}/adversarial/rebuttal")
async def submit_rebuttal(decision_id: str, payload: RebuttalCreate, db: Session = Depends(get_db)):
    """
    Evaluate the user's rebuttal to a specific adversarial question.
    """
    # In a real scenario, we'd fetch the actual question text from the DB
    # For MVP, we'll assume the user sends the question ID and rebuttal

    # Logic: Get the original question (simulated here)
    question_text = "Simulated critical question from the skeptic"

    evaluation = ai_skeptic_service.evaluate_rebuttal(question_text, payload.rebuttal)

    # Store rebuttal and evaluation
    DecisionService(db).add_step(decision_id, "Rebuttal_Evaluation", {
        "question_id": payload.question_id,
        "rebuttal": payload.rebuttal,
        "evaluation": evaluation
    })

    return evaluation
