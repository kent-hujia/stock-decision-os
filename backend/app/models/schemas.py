from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# Single-user for now, so decisions carry no user id. The journal tables use new
# names so they don't collide with the old UUID-keyed "decisions" tables that
# create_all can't migrate in existing databases.


class Decision(Base):
    """An investment thesis for one stock, plus everything that happened to it."""
    __tablename__ = "journal_decisions"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    stock_name = Column(String, nullable=False)
    thesis = Column(Text, nullable=False)
    conviction = Column(Integer, nullable=False)  # 1-10
    monitor_status = Column(String, nullable=False, default="none")  # none, pending, done, error
    monitor_error = Column(String)
    monitor_started_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    steps = relationship("DecisionStep", cascade="all, delete-orphan", order_by="DecisionStep.id")
    monitors = relationship("ThesisMonitor", cascade="all, delete-orphan", order_by="ThesisMonitor.id")
    reviews = relationship("SkepticReview", cascade="all, delete-orphan", order_by="SkepticReview.id")


class DecisionStep(Base):
    """Append-only history entry (created, skeptic_questions, rebuttal_graded, ...)."""
    __tablename__ = "journal_steps"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("journal_decisions.id", ondelete="CASCADE"), index=True, nullable=False)
    step_type = Column(String, nullable=False)
    content = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ThesisMonitor(Base):
    """A condition that should keep holding if the thesis is right, e.g. revenue_yoy >= 10."""
    __tablename__ = "thesis_monitors"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("journal_decisions.id", ondelete="CASCADE"), index=True, nullable=False)
    metric = Column(String, nullable=False)  # key of thesis_monitor.METRICS
    operator = Column(String, nullable=False)  # ">=" or "<="
    threshold = Column(Float, nullable=False)
    rationale = Column(Text)
    source = Column(String, nullable=False, default="manual")  # ai, manual
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SkepticReview(Base):
    """One round of three Claude challenge questions grounded in the stock's X-ray data."""
    __tablename__ = "skeptic_reviews"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("journal_decisions.id", ondelete="CASCADE"), index=True, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, done, error
    questions = Column(JSON)
    data_as_of = Column(JSON)
    error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    answers = relationship("SkepticAnswer", cascade="all, delete-orphan", order_by="SkepticAnswer.id")


class SkepticAnswer(Base):
    """The user's rebuttal to one question and Claude's Pass/Fail grade."""
    __tablename__ = "skeptic_answers"
    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("skeptic_reviews.id", ondelete="CASCADE"), index=True, nullable=False)
    question_index = Column(Integer, nullable=False)
    rebuttal = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, done, error
    verdict = Column(String)  # Pass, Fail
    reason = Column(Text)
    error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AiReport(Base):
    """One Claude-written revenue X-ray reading per stock per day (cached to limit API cost)."""
    __tablename__ = "ai_reports"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    report_date = Column(String, index=True, nullable=False)  # Taiwan date, YYYY-MM-DD
    status = Column(String, nullable=False, default="pending")  # pending, done, error
    content = Column(JSON)
    error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
