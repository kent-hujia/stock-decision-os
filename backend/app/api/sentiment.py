from fastapi import APIRouter, HTTPException
from app.services.sentiment import sentiment_service
from typing import Dict, Any

router = APIRouter()

@router.get("/{ticker}")
async def get_sentiment(ticker: str):
    """
    Fetch sentiment analysis, Z-Score, and conviction divergence for a specific ticker.
    """
    try:
        analysis = sentiment_service.analyze_divergence(ticker)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing sentiment for {ticker}: {str(e)}")
