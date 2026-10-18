from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SentimentLog(Base):
    __tablename__ = "sentiment_logs"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    retail_score = Column(Float)
    inst_score = Column(Float)
    z_score = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    ticker = Column(String, index=True, nullable=False)
    status = Column(String, default="Triage") # Triage, DeepDive, Adversarial, Gate, Completed
    conviction = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class DecisionStep(Base):
    __tablename__ = "decision_steps"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decisions.id"))
    step_type = Column(String, nullable=False) # Triage, Skeptic_Review, etc.
    content = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Thesis(Base):
    __tablename__ = "theses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decisions.id"))
    hypothesis = Column(String, nullable=False)
    trigger_metric = Column(String)
    trigger_value = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RevenueSnapshot(Base):
    __tablename__ = "revenue_snapshots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String, index=True, nullable=False)
    story_line = Column(JSON)
    quality_score = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
