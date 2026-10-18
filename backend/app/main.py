from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import decision, stocks
from app.models.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

# CORS setup for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, specify the actual frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["stocks"])
app.include_router(decision.router, prefix="/api/v1/decision", tags=["decision"])

@app.get("/")
def root():
    return {"message": "Welcome to the Stock Decision OS API"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "0.2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
