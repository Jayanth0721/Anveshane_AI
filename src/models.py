from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class DecisionStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class Evidence(BaseModel):
    """Evidence linking decision to source document"""
    criterion_id: str
    criterion_name: str
    source_document: str
    page_number: int
    extracted_text: str
    confidence: float  # 0.0 to 1.0
    reasoning: str


class CriterionEvaluation(BaseModel):
    """Evaluation result for a single criterion"""
    criterion_id: str
    criterion_name: str
    status: DecisionStatus
    evidence: List[Evidence]
    confidence: float
    reason: str


class BidderEvaluationResult(BaseModel):
    """Complete evaluation result for a bidder"""
    bidder_name: str
    tender_id: str
    final_decision: DecisionStatus
    overall_confidence: float
    criterion_evaluations: List[CriterionEvaluation]
    summary: str
    timestamp: datetime
    audit_id: str


class EligibilityCriterion(BaseModel):
    """Eligibility criterion extracted from tender"""
    criterion_id: str
    name: str
    description: str
    required: bool  # Knock-out criterion
    data_type: str  # e.g., "currency", "text", "date", "boolean"
    expected_value: Optional[str]
    source_page: int


class TenderDocument(BaseModel):
    """Parsed tender document"""
    tender_id: str
    title: str
    criteria: List[EligibilityCriterion]
    raw_text: str
    extraction_confidence: float


class BidderSubmission(BaseModel):
    """Parsed bidder submission"""
    bidder_name: str
    submission_date: datetime
    extracted_fields: Dict[str, Any]
    raw_text: str
    extraction_confidence: float
    source_document: str


class AuditLog(BaseModel):
    """Audit trail entry"""
    timestamp: datetime
    action: str
    user_id: Optional[str]
    bidder_name: str
    tender_id: str
    decision: DecisionStatus
    reason: str
    override: bool = False
    audit_id: str
