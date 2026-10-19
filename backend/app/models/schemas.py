from sqlalchemy import Boolean, Column, String, Integer, Float, ForeignKey, DateTime, JSON, LargeBinary, Text
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


class AiReading(Base):
    """A cached daily Claude reading of one stock, keyed by kind (e.g. "swing")."""
    __tablename__ = "ai_readings"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, index=True, nullable=False)
    ticker = Column(String, index=True, nullable=False)
    report_date = Column(String, index=True, nullable=False)  # Taiwan date, YYYY-MM-DD
    status = Column(String, nullable=False, default="pending")  # pending, done, error
    content = Column(JSON)
    error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PaperAccount(Base):
    """The single practice account: virtual cash, real prices."""
    __tablename__ = "paper_accounts"
    id = Column(Integer, primary_key=True)
    initial_cash = Column(Float, nullable=False, default=1_000_000)
    risk_pct = Column(Float, nullable=False, default=2.0)  # max loss per trade, % of equity
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaperTrade(Base):
    """One swing trade from plan to review. Fills are simulated on real daily OHLC bars."""
    __tablename__ = "paper_trades"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    stock_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="planned")  # planned, open, closed, cancelled
    thesis = Column(Text, nullable=False)
    order_type = Column(String, nullable=False)  # market (next open) or limit
    limit_price = Column(Float)
    ref_price = Column(Float, nullable=False)  # last close when planned
    ref_date = Column(String, nullable=False)
    plan_date = Column(String, nullable=False)  # Taiwan date; only later bars can fill the order
    expire_days = Column(Integer, nullable=False, default=5)  # unfilled orders cancel after N bars
    initial_stop = Column(Float, nullable=False)
    stop_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    checklist = Column(JSON)  # swing checks + defense levels at planning time
    last_synced_date = Column(String)  # last bar already processed
    entry_date = Column(String)
    entry_price = Column(Float)
    entry_fee = Column(Float)
    high_since_entry = Column(Float)
    low_since_entry = Column(Float)
    exit_requested_date = Column(String)  # manual exit fills at the next bar's open
    exit_date = Column(String)
    exit_price = Column(Float)
    exit_fee = Column(Float)
    exit_tax = Column(Float)
    exit_reason = Column(String)  # stop, target, manual
    cancel_reason = Column(String)
    followed_plan = Column(Boolean)
    mistakes = Column(JSON)
    lesson = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    critique_status = Column(String, nullable=False, default="none")  # none, pending, done, error
    critique = Column(JSON)
    critique_error = Column(String)
    critique_started_at = Column(DateTime(timezone=True))
    ai_review_status = Column(String, nullable=False, default="none")
    ai_review = Column(JSON)
    ai_review_error = Column(String)
    ai_review_started_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    events = relationship("PaperTradeEvent", cascade="all, delete-orphan", order_by="PaperTradeEvent.id")


class PaperTradeEvent(Base):
    """Append-only history of a trade: planned, filled, stop_moved, alert, closed, reviewed, ..."""
    __tablename__ = "paper_trade_events"
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(Integer, ForeignKey("paper_trades.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type = Column(String, nullable=False)
    bar_date = Column(String)  # trading day the event refers to, if any
    content = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    """One run of a scheduled job, so it runs once per Taiwan date even across restarts."""
    __tablename__ = "job_runs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    run_date = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)  # done, error
    detail = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EarningsCall(Base):
    """An uploaded earnings-call (法說會) slide deck and Claude's breakdown of it."""
    __tablename__ = "earnings_calls"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    pdf = Column(LargeBinary, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, done, error
    content = Column(JSON)
    error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
