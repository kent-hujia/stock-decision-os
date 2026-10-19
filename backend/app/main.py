from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import decisions, notify, paper, stocks
from app.services.notify import start_scheduler
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
app.include_router(notify.router, prefix="/api/v1/notify", tags=["notify"])
app.include_router(paper.router, prefix="/api/v1/paper", tags=["paper"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["decisions"])

@app.on_event("startup")
def _start_jobs():
    start_scheduler()


@app.get("/")
def root():
    return {"message": "Welcome to the Stock Decision OS API"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "0.2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
