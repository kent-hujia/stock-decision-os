from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.services.revenue import revenue_analysis_service
from app.models.schemas import RevenueSnapshot
import uuid

router = APIRouter()

@router.post("/{ticker}/analyze")
def trigger_revenue_analysis(ticker: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Trigger an asynchronous AI revenue analysis.
    """
    # In a full implementation, this would be a Celery task.
    # For MVP, we'll use FastAPI's BackgroundTasks.
    background_tasks.add_task(perform_analysis, ticker, db)
    return {"message": f"Analysis for {ticker} started in background. Please check back in a few moments."}

@router.get("/{ticker}")
def get_revenue_analysis(ticker: str, db: Session = Depends(get_db)):
    """
    Fetch the latest revenue X-ray snapshot.
    """
    snapshot = db.query(RevenueSnapshot).filter(RevenueSnapshot.ticker == ticker).order_by(RevenueSnapshot.timestamp.desc()).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="No analysis found for this ticker. Please trigger analysis first.")
    return snapshot

def perform_analysis(ticker: str, db: Session):
    """
    The actual background worker logic.
    """
    result = revenue_analysis_service.analyze_revenue_quality(ticker)
    if "error" in result:
        return

    # Save to DB
    snapshot = RevenueSnapshot(
        id=uuid.uuid4(),
        ticker=ticker,
        story_line=result['storyline'],
        quality_score=result['quality_score']
    )
    db.add(snapshot)
    db.commit()
