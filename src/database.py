"""
Database models and configuration
"""
from sqlalchemy import create_engine, Column, String, DateTime, Float, Boolean, Integer, Text, Enum, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import enum

DATABASE_URL = "sqlite:///./tender_system.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    # SQLite performance: WAL mode allows concurrent reads, pool_pre_ping avoids stale connections
    pool_pre_ping=True,
)

# Enable WAL mode and other SQLite performance pragmas on every new connection
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")   # concurrent reads
    cursor.execute("PRAGMA synchronous=NORMAL") # faster writes, still safe
    cursor.execute("PRAGMA cache_size=-64000")  # 64 MB page cache
    cursor.execute("PRAGMA temp_store=MEMORY")  # temp tables in RAM
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CONTRACTOR = "contractor"
    EVALUATOR = "evaluator"
    CITIZEN = "citizen"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.CONTRACTOR, index=True)
    company_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Contractor Performance Stats
    merit_points = Column(Float, default=0.0)
    demerit_points = Column(Float, default=0.0)
    on_time_completions = Column(Integer, default=0)
    total_projects = Column(Integer, default=0)


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text)
    department = Column(String, nullable=True)
    created_by = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    document_path = Column(String)
    status = Column(String, default="active", index=True)
    sector = Column(String, nullable=True, index=True)
    criteria_count = Column(Integer, default=0)
    duration_days = Column(Integer, nullable=True)
    investment_amount = Column(String, nullable=True)
    penalty_per_day = Column(String, nullable=True)
    penalty_max_days = Column(Integer, default=180)
    work_location = Column(String, nullable=True)
    application_deadline = Column(DateTime, nullable=True)
    awarded_to = Column(String, nullable=True)
    awarded_at = Column(DateTime, nullable=True)
    delay_days = Column(Integer, default=0)
    penalty_applied = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)


class BidderSubmission(Base):
    __tablename__ = "bidder_submissions"

    id = Column(String, primary_key=True, index=True)
    tender_id = Column(String, index=True)
    bidder_id = Column(String, index=True)
    bidder_name = Column(String)
    company_name = Column(String)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    document_path = Column(String)
    status = Column(String, default="submitted", index=True)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(String, primary_key=True, index=True)
    tender_id = Column(String, index=True)
    submission_id = Column(String, index=True)
    bidder_name = Column(String)
    decision = Column(String, index=True)   # ELIGIBLE, NOT_ELIGIBLE, MANUAL_REVIEW
    confidence = Column(Float, index=True)  # indexed for ORDER BY confidence DESC
    summary = Column(Text)
    criteria_breakdown = Column(Text)       # JSON
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    evaluated_by = Column(String, nullable=True)
    audit_id = Column(String, unique=True)


class Override(Base):
    __tablename__ = "overrides"

    id = Column(String, primary_key=True, index=True)
    evaluation_id = Column(String, index=True)
    original_decision = Column(String)
    new_decision = Column(String)
    reason = Column(Text)
    overridden_by = Column(String)
    overridden_at = Column(DateTime, default=datetime.utcnow)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    username = Column(String)
    role = Column(String)
    subject = Column(String)
    message = Column(Text)
    priority = Column(String, default="low")
    status = Column(String, default="active")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TicketReply(Base):
    __tablename__ = "ticket_replies"

    id = Column(String, primary_key=True, index=True)
    ticket_id = Column(String, index=True)
    user_id = Column(String)
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)


# Composite indexes for the most common query patterns
Index("ix_eval_tender_decision",    Evaluation.tender_id, Evaluation.decision)
Index("ix_eval_tender_confidence",  Evaluation.tender_id, Evaluation.confidence)
Index("ix_sub_tender_status",       BidderSubmission.tender_id, BidderSubmission.status)


def init_db():
    """Initialize database and create all tables/indexes"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency: yield a DB session, always close on exit"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
