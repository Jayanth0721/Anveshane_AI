"""
Pydantic schemas for API requests/responses
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# Auth Schemas
class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str
    company_name: Optional[str] = None
    role: str = "contractor"  # contractor or admin


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    role: str
    company_name: Optional[str]
    created_at: datetime


class UserProfileUpdate(BaseModel):
    full_name: str
    username: str
    email: EmailStr
    company_name: Optional[str] = None


# Tender Schemas
class TenderCreate(BaseModel):
    title: str
    description: str
    sector: Optional[str] = "Infrastructure"


class TenderResponse(BaseModel):
    id: str
    title: str
    description: str
    sector: Optional[str] = None
    created_by: str
    created_at: datetime
    status: str
    criteria_count: int


class TenderDetailResponse(TenderResponse):
    document_path: str
    submissions_count: int = 0


# Submission Schemas
class SubmissionResponse(BaseModel):
    id: str
    tender_id: str
    bidder_name: str
    company_name: str
    submitted_at: datetime
    status: str


# Evaluation Schemas
class EvaluationResponse(BaseModel):
    id: str
    tender_id: str
    submission_id: str
    bidder_name: str
    decision: str
    confidence: float
    summary: str
    evaluated_at: datetime
    audit_id: str


class EvaluationDetailResponse(EvaluationResponse):
    criteria_breakdown: dict


# Override Schemas
class OverrideRequest(BaseModel):
    new_decision: str
    reason: str


class OverrideResponse(BaseModel):
    id: str
    evaluation_id: str
    original_decision: str
    new_decision: str
    reason: str
    overridden_at: datetime


# Dashboard Schemas
class DashboardStats(BaseModel):
    total_tenders: int
    active_tenders: int
    total_submissions: int
    pending_evaluations: int
    approved_bidders: int
    rejected_bidders: int


class TenderStats(BaseModel):
    tender_id: str
    tender_title: str
    total_submissions: int
    evaluated: int
    pending: int
    approved: int
    rejected: int
    manual_review: int


class AdminAnalytics(BaseModel):
    total_users: int
    contractors: int
    admins: int
    total_tenders: int
    total_evaluations: int
    average_confidence: float
    manual_review_rate: float


# Citizen Transparency Schemas
class CitizenTenderListItem(BaseModel):
    tender_id: str
    title: str
    department: str
    status: str
    sector: Optional[str] = "General"
    deadline: Optional[datetime] = None



class CitizenComparisonRow(BaseModel):
    bidder: str
    status: str
    key_strength: str


class CitizenTenderDetail(BaseModel):
    tender_id: str
    title: str
    winning_bidder: str
    top_bidders: List[str]
    contract_value: str
    duration: str
    status: str
    delay_days: int
    penalty_applied: bool
    last_updated: datetime
    comparative_table: List[CitizenComparisonRow]
    verified_decision: bool = True


class CitizenTenderExplanation(BaseModel):
    winner: str
    reasons: List[str]
    confidence: float


# Support Ticket Schemas
class TicketReplyResponse(BaseModel):
    id: str
    ticket_id: str
    user_id: str
    message: str
    sent_at: datetime


class TicketResponse(BaseModel):
    id: str
    user_id: str
    username: str
    role: str
    subject: str
    message: str
    priority: str
    status: str
    is_read: bool
    created_at: datetime
    replies: List[TicketReplyResponse] = []


class TicketCreate(BaseModel):
    subject: str
    message: str
    priority: str = "low"


class TicketReplyCreate(BaseModel):
    message: str
