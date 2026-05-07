"""
Enhanced FastAPI backend with authentication and dashboard
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import tempfile
import os
import json
import uuid
import sqlite3
import re
from datetime import datetime, timedelta
from pathlib import Path
import PyPDF2
from dotenv import load_dotenv
load_dotenv()


from src.database import init_db, get_db, User, Tender, BidderSubmission, Evaluation, Override, UserRole, SupportTicket, TicketReply
from src.auth import hash_password, verify_password, create_access_token, verify_token, generate_user_id
from src.schemas import (
    UserRegister, UserLogin, TenderCreate, TenderResponse, SubmissionResponse,
    EvaluationResponse, OverrideRequest, DashboardStats, AdminAnalytics, UserProfileUpdate,
    TicketCreate, TicketReplyCreate, TicketResponse, TicketReplyResponse
)
from src.audit_logger import AuditLogger

audit_logger = AuditLogger()
from src.citizen_service import (
    get_public_tender_detail as build_citizen_tender_detail,
    get_public_tender_explanation as build_citizen_tender_explanation,
    list_public_tenders,
    PUBLISHED_STATUSES,
)
from src.main import TenderEvaluator

app = FastAPI(
    title="Tender Evaluation Dashboard API",
    description="AI-powered procurement evaluation with dashboard",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

evaluator = TenderEvaluator()
CONTRACTOR_UPLOADS_DIR = Path("uploads/contractor")
CONTRACTOR_ANALYSIS_RESULTS = {}

SECTOR_DASHBOARD_DATA = [
    {
        "sector": "Infrastructure",
        "percentage": 40,
        "tender_count": 120,
        "description": "Roads, construction, water supply",
    },
    {
        "sector": "TECH",
        "percentage": 30,
        "tender_count": 75,
        "description": "Manpower, digital systems, hardware, service delivery",
    },
    {
        "sector": "Education",
        "percentage": 10,
        "tender_count": 26,
        "description": "School development, devices, books, uniforms, nutrition support",
    },
    {
        "sector": "Agriculture",
        "percentage": 10,
        "tender_count": 30,
        "description": "Watershed, farming equipment",
    },
    {
        "sector": "Insurance",
        "percentage": 10,
        "tender_count": 20,
        "description": "Mediclaim policies",
    },
]

SECTOR_TENDER_DETAILS = {
    "Infrastructure": [
        {"tender_id": "INF-101", "title": "State Highway Resurfacing Package", "department": "PWD", "status": "ongoing"},
        {"tender_id": "INF-102", "title": "Urban Water Supply Expansion", "department": "Urban Development", "status": "completed"},
        {"tender_id": "INF-103", "title": "District Bridge Rehabilitation", "department": "Rural Works", "status": "ongoing"},
    ],
    "TECH": [
        {"tender_id": "OUT-201", "title": "Citizen Contact Center Operations", "department": "e-Governance", "status": "completed"},
        {"tender_id": "OUT-202", "title": "District Manpower Support Services", "department": "Administration", "status": "ongoing"},
        {"tender_id": "TECH-302", "title": "Data Center Modernization", "department": "IT", "status": "ongoing"},
        {"tender_id": "TECH-303", "title": "State Network and Server Infrastructure Upgrade", "department": "IT", "status": "ongoing"},
    ],
    "Education": [
        {"tender_id": "EDU-301", "title": "School Device Procurement", "department": "Education", "status": "completed"},
        {
            "tender_id": "EDU-303",
            "title": "Government Education Institution Support for School Development, Books, Uniforms, Sports Kits and Food Funding",
            "department": "Education",
            "status": "ongoing",
        },
        {
            "tender_id": "EDU-304",
            "title": "Government School Library Books and Student Uniform Supply",
            "department": "Education",
            "status": "ongoing",
        },
    ],
    "Agriculture": [
        {"tender_id": "AGR-401", "title": "Watershed Monitoring Equipment", "department": "Agriculture", "status": "ongoing"},
        {"tender_id": "AGR-402", "title": "Farm Mechanization Kit Supply", "department": "Horticulture", "status": "completed"},
    ],
    "Insurance": [
        {"tender_id": "INS-501", "title": "State Health Mediclaim Policy", "department": "Health", "status": "completed"},
        {"tender_id": "INS-502", "title": "Crop Loss Coverage Renewal", "department": "Agriculture", "status": "ongoing"},
    ],
}

# Runtime migration for older SQLite files before SQLAlchemy touches the models.
def ensure_runtime_schema():
    conn = sqlite3.connect("tender_system.db")
    cur = conn.cursor()

    existing = {row[1] for row in cur.execute("PRAGMA table_info(tenders)").fetchall()}
    new_columns = [
        ("department", "TEXT"),
        ("delay_days", "INTEGER DEFAULT 0"),
        ("penalty_applied", "BOOLEAN DEFAULT 0"),
        ("last_updated", "DATETIME"),
        ("application_deadline", "DATETIME"),
        ("sector", "TEXT"),
    ]

    for column_name, column_type in new_columns:
        if column_name not in existing:
            cur.execute(f"ALTER TABLE tenders ADD COLUMN {column_name} {column_type}")

    # Users Table Stats
    cur.execute("PRAGMA table_info(users)")
    existing_users = {row[1] for row in cur.fetchall()}
    user_stats = [
        ("merit_points", "FLOAT DEFAULT 0.0"),
        ("demerit_points", "FLOAT DEFAULT 0.0"),
        ("on_time_completions", "INTEGER DEFAULT 0"),
        ("total_projects", "INTEGER DEFAULT 0"),
    ]
    for col, col_type in user_stats:
        if col not in existing_users:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()


def require_auth(token: str):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    return token_data


def require_roles(token: str, allowed_roles):
    token_data = require_auth(token)
    if token_data.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return token_data


def parse_optional_datetime(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid application deadline")


def parse_money_to_rupees(value: str):
    if not value:
        return None
    text = str(value).replace(",", "").lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|lac|million|billion)?", text)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or ""
    multiplier = 1
    if unit in {"crore", "cr"}:
        multiplier = 10_000_000
    elif unit in {"lakh", "lakhs", "lac"}:
        multiplier = 100_000
    elif unit == "million":
        multiplier = 1_000_000
    elif unit == "billion":
        multiplier = 1_000_000_000
    return amount * multiplier


def extract_proposal_insights(text: str):
    clean = re.sub(r"\s+", " ", text or "")
    amount_patterns = [
        r"(?i)(?:bid|quoted|proposal|contract|project|commercial|amount|price|cost|value)[^.\n]{0,80}?(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|lac|million|billion)?",
        r"(?i)(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|lac|million|billion)?",
    ]
    timeline_patterns = [
        r"(?i)(?:complete|finish|deliver|duration|timeline|delivery|implementation)[^.\n]{0,80}?(\d{1,4})\s*(days?|months?|weeks?)",
        r"(?i)(\d{1,4})\s*(days?|months?|weeks?)\s+(?:to\s+)?(?:complete|finish|deliver|implement)",
    ]

    amount_text = None
    amount_rupees = None
    for pattern in amount_patterns:
        match = re.search(pattern, clean)
        if match:
            unit = match.group(2) or ""
            amount_text = f"INR {match.group(1)} {unit}".strip()
            amount_rupees = parse_money_to_rupees(amount_text)
            break

    completion_days = None
    completion_text = None
    for pattern in timeline_patterns:
        match = re.search(pattern, clean)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            if "month" in unit:
                completion_days = value * 30
            elif "week" in unit:
                completion_days = value * 7
            else:
                completion_days = value
            completion_text = f"{value} {unit}"
            break

    proposal_summary = []
    if amount_text:
        proposal_summary.append(f"Quoted amount: {amount_text}")
    if completion_text:
        proposal_summary.append(f"Completion timeline: {completion_text}")
    if not proposal_summary:
        proposal_summary.append("Proposal amount or completion timeline was not clearly found")

    return {
        "amount_text": amount_text or "Not found",
        "amount_rupees": amount_rupees,
        "completion_days": completion_days,
        "completion_text": completion_text or "Not found",
        "proposal_summary": "; ".join(proposal_summary),
    }


def calculate_smart_score(base_confidence: float, tender, proposal: dict):
    compliance_score = max(0.0, min(1.0, base_confidence or 0.0))
    weights = {"compliance": 0.7, "amount": 0.0, "timeline": 0.0}

    amount_score = 0.0
    tender_budget = parse_money_to_rupees(tender.investment_amount)
    bid_amount = proposal.get("amount_rupees")
    if tender_budget and bid_amount:
        ratio = bid_amount / tender_budget
        if ratio <= 1:
            amount_score = max(0.65, 1 - (ratio * 0.25))
        else:
            amount_score = max(0.0, 1 - ((ratio - 1) * 1.5))
        weights["compliance"] -= 0.25
        weights["amount"] = 0.25

    timeline_score = 0.0
    duration_days = tender.duration_days or 0
    completion_days = proposal.get("completion_days")
    if duration_days and completion_days:
        ratio = completion_days / duration_days
        if ratio <= 1:
            timeline_score = max(0.7, 1 - (ratio * 0.2))
        else:
            timeline_score = max(0.0, 1 - ((ratio - 1) * 1.2))
        weights["compliance"] -= 0.15
        weights["timeline"] = 0.15

    score = (
        compliance_score * weights["compliance"]
        + amount_score * weights["amount"]
        + timeline_score * weights["timeline"]
    )
    return round(max(0.0, min(1.0, score)), 2)


def tender_is_published(tender: Tender) -> bool:
    return (tender.status or "").lower() == "published"


def build_tender_timeline(
    db: Session,
    tender: Tender,
    token_data,
):
    role = token_data.role
    is_public_view = role == "citizen"

    submissions = (
        db.query(BidderSubmission)
        .filter(BidderSubmission.tender_id == tender.id)
        .order_by(BidderSubmission.submitted_at.asc())
        .all()
    )
    evaluations = (
        db.query(Evaluation)
        .filter(Evaluation.tender_id == tender.id)
        .order_by(Evaluation.evaluated_at.asc())
        .all()
    )
    overrides = (
        db.query(Override)
        .join(Evaluation, Evaluation.id == Override.evaluation_id)
        .filter(Evaluation.tender_id == tender.id)
        .order_by(Override.overridden_at.asc())
        .all()
    )

    own_submission_ids = {
        sub.id for sub in submissions if sub.bidder_id == token_data.user_id
    } if role == "contractor" else set()

    items = [{
        "type": "created",
        "at": tender.created_at.isoformat(),
        "title": "Tender created",
        "description": f"{tender.title} was created in {tender.department or 'Procurement Department'}.",
    }]

    if tender.application_deadline:
        items.append({
            "type": "deadline",
            "at": tender.application_deadline.isoformat(),
            "title": "Application deadline set",
            "description": "The tender submission deadline was scheduled.",
        })

    for submission in submissions:
        if role == "admin":
            description = f"{submission.bidder_name} ({submission.company_name}) submitted a proposal."
        elif role == "contractor" and submission.id in own_submission_ids:
            description = "Your bid was submitted successfully."
        elif is_public_view:
            description = "A bidder submission was received during the tender process."
        else:
            description = "A bidder submission was received."

        items.append({
            "type": "submission",
            "at": submission.submitted_at.isoformat(),
            "title": "Bid submission received",
            "description": description,
        })

    for evaluation in evaluations:
        related_submission = next((sub for sub in submissions if sub.id == evaluation.submission_id), None)
        if role == "admin":
            description = f"{evaluation.bidder_name} was marked {evaluation.decision.replace('_', ' ').title()} by AI evaluation."
        elif role == "contractor" and evaluation.submission_id in own_submission_ids and tender_is_published(tender):
            description = f"Your submission was evaluated as {evaluation.decision.replace('_', ' ').title()}."
        elif is_public_view:
            description = "An AI evaluation step was completed for a bidder submission."
        else:
            description = "A bid evaluation was completed."

        if role == "contractor" and evaluation.submission_id not in own_submission_ids and related_submission:
            description = "A bid evaluation was completed."

        items.append({
            "type": "evaluation",
            "at": evaluation.evaluated_at.isoformat(),
            "title": "AI evaluation completed",
            "description": description,
        })

    for override in overrides:
        if role == "admin":
            description = f"An admin changed a decision from {override.original_decision.replace('_', ' ').title()} to {override.new_decision.replace('_', ' ').title()}."
        else:
            description = "An admin review adjusted an evaluation decision."

        items.append({
            "type": "override",
            "at": override.overridden_at.isoformat(),
            "title": "Admin review update",
            "description": description,
        })

    if tender.status == "closed":
        items.append({
            "type": "closed",
            "at": (tender.last_updated or tender.updated_at or datetime.utcnow()).isoformat(),
            "title": "Tender closed for review",
            "description": "Applications were closed and the tender moved into final review.",
        })

    if tender.awarded_at:
        publish_description = (
            f"The result was published with {tender.awarded_to or 'the selected bidder'} as the awardee."
            if role in {"admin", "citizen"} or tender_is_published(tender)
            else "The tender result was published."
        )
        items.append({
            "type": "published",
            "at": tender.awarded_at.isoformat(),
            "title": "Result published",
            "description": publish_description,
        })

    items.sort(key=lambda item: item["at"])
    return items


def serialize_tender(tender: Tender, db: Session):
    result = {
        "id": tender.id,
        "title": tender.title,
        "description": tender.description,
        "department": tender.department,
        "sector": tender.sector,
        "status": tender.status,
        "created_at": tender.created_at.isoformat(),
        "duration_days": tender.duration_days,
        "investment_amount": tender.investment_amount,
        "penalty_per_day": tender.penalty_per_day,
        "penalty_max_days": tender.penalty_max_days,
        "work_location": tender.work_location,
        "application_deadline": (
            tender.application_deadline.isoformat() if tender.application_deadline else None
        ),
        "awarded_to": tender.awarded_to,
        "awarded_at": tender.awarded_at.isoformat() if tender.awarded_at else None,
        "submissions": db.query(BidderSubmission).filter(
            BidderSubmission.tender_id == tender.id
        ).count(),
    }

    if tender.status == "published":
        evals = db.query(Evaluation).filter(Evaluation.tender_id == tender.id).order_by(Evaluation.confidence.desc()).all()
        # Find eligible runners-up, ensuring we skip whoever actually won
        eligible_runners = []
        for e in evals:
            if e.decision == "ELIGIBLE" and e.bidder_name != tender.awarded_to:
                # To prevent duplicates from the same bidder submitting twice
                if e.bidder_name not in eligible_runners:
                    eligible_runners.append(e.bidder_name)
                    
        result["runner_up"] = eligible_runners[0] if len(eligible_runners) > 0 else None
        result["second_runner_up"] = eligible_runners[1] if len(eligible_runners) > 1 else None
    else:
        result["runner_up"] = None
        result["second_runner_up"] = None

    return result


def extract_pdf_text(pdf_path: str) -> str:
    text_chunks = []
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text_chunks.append(page.extract_text() or "")
    except Exception:
        return ""
    return "\n".join(text_chunks).strip()


def extract_bidder_name(text: str) -> str:
    patterns = [
        r"(?i)bidder\s+name\s*[:\-]\s*([A-Za-z0-9&.,()' /\-]{3,80})",
        r"(?i)company\s+name\s*[:\-]\s*([A-Za-z0-9&.,()' /\-]{3,80})",
        r"(?i)m/s\.?\s*([A-Za-z0-9&.,()' /\-]{3,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" .,-")
    return ""


def extract_turnover(text: str) -> str:
    patterns = [
        r"(?i)(?:turnover|revenue)[^\n:]{0,40}[:\-]?\s*((?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?\s*(?:Cr|Crore|Lakh|Lakhs|Million|Billion)?)",
        r"((?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?\s*(?:Cr|Crore|Lakh|Lakhs|Million|Billion))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def extract_certifications(text: str):
    certifications = []
    text_upper = text.upper()

    if re.search(r"\bGST\b|\bGSTIN\b", text_upper):
        certifications.append("GST")

    iso_matches = re.findall(r"\bISO\s*[-:]?\s*(\d{4,5}(?::\d{4})?)", text_upper)
    if iso_matches:
        certifications.extend([f"ISO {value}" for value in iso_matches[:3]])
    elif "ISO" in text_upper:
        certifications.append("ISO")

    unique = []
    for item in certifications:
        if item not in unique:
            unique.append(item)
    return unique


def extract_project_references(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    project_lines = [
        line for line in lines
        if re.search(r"(?i)\b(project|projects|reference|references|work order|contract)\b", line)
    ]
    if project_lines:
        return " | ".join(project_lines[:3])[:400]
    return ""


def classify_sector(text: str) -> str:
    sector_keywords = {
        "Infrastructure": ["road", "construction", "water", "drainage"],
        "Technology": ["software", "hardware", "it"],
        "Agriculture": ["agriculture", "farm", "watershed"],
        "Outsourcing": ["manpower", "service", "call center"],
        "Insurance": ["insurance", "policy"],
    }
    text_lower = text.lower()
    scores = {}
    for sector, keywords in sector_keywords.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score:
            scores[sector] = score

    if not scores:
        return "General"
    return max(scores, key=scores.get)


def classify_citizen_dashboard_sector(tender: Tender) -> str:
    source_text = " ".join(
        filter(
            None,
            [
                tender.title or "",
                tender.description or "",
                tender.department or "",
                tender.work_location or "",
            ],
        )
    ).lower()

    if any(keyword in source_text for keyword in ["education", "school", "student", "books", "uniform", "sports kit", "midday meal", "food"]):
        return "Education"

    base_sector = classify_sector(source_text)
    if base_sector in {"Technology", "Outsourcing"}:
        return "TECH"
    return base_sector


def build_document_summary(text: str, sector: str, bidder_name: str) -> str:
    sentences = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
        if segment.strip()
    ]
    first_sentence = sentences[0] if sentences else "Tender document analyzed for key procurement signals."
    subject = bidder_name or "This document"
    return f"{subject} appears to relate to the {sector.lower()} sector. {first_sentence[:220]}"


def determine_eligibility_status(turnover: str, certifications, projects: str, sector: str, text: str) -> str:
    signals = 0
    if turnover:
        signals += 1
    if certifications:
        signals += 1
    if projects:
        signals += 1
    if sector != "General":
        signals += 1

    if not text.strip():
        return "Not Eligible"
    if signals >= 3:
        return "Eligible"
    if signals >= 1:
        return "Review"
    return "Not Eligible"


def calculate_analysis_confidence(turnover: str, certifications, projects: str, sector: str, text: str) -> float:
    confidence = 0.35
    if text.strip():
        confidence += 0.15
    if sector != "General":
        confidence += 0.2
    if turnover:
        confidence += 0.1
    if certifications:
        confidence += 0.1
    if projects:
        confidence += 0.1
    return round(min(confidence, 0.95), 2)


ensure_runtime_schema()
init_db()


# ============================================================================
# CONTRACTOR DOCUMENT ANALYSIS
# ============================================================================

@app.post("/api/contractor/upload")
async def upload_contractor_document(
    file: UploadFile = File(...),
    token: str = None,
):
    """Upload contractor PDF document for analysis."""
    require_roles(token, {"contractor"})

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    CONTRACTOR_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    safe_name = Path(file.filename).name
    file_path = CONTRACTOR_UPLOADS_DIR / f"{file_id}_{safe_name}"

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to save file: {exc}")

    CONTRACTOR_ANALYSIS_RESULTS[file_id] = {
        "file_id": file_id,
        "file_name": safe_name,
        "file_path": str(file_path),
        "uploaded_at": datetime.utcnow().isoformat(),
    }

    return {
        "status": "success",
        "file_id": file_id,
        "file_name": safe_name,
    }


@app.post("/api/contractor/analyze/{file_id}")
async def analyze_contractor_document(
    file_id: str,
    token: str = None,
):
    """Analyze uploaded contractor document with lightweight keyword logic."""
    require_roles(token, {"contractor"})

    file_record = CONTRACTOR_ANALYSIS_RESULTS.get(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    text = extract_pdf_text(file_record["file_path"])
    bidder_name = extract_bidder_name(text)
    turnover = extract_turnover(text)
    certifications = extract_certifications(text)
    projects = extract_project_references(text)
    sector = classify_sector(text)
    summary = build_document_summary(text, sector, bidder_name)
    eligibility_status = determine_eligibility_status(turnover, certifications, projects, sector, text)
    confidence = calculate_analysis_confidence(turnover, certifications, projects, sector, text)

    analysis_result = {
        "file_id": file_id,
        "sector": sector,
        "summary": summary,
        "extracted_data": {
            "bidder_name": bidder_name or "Not found",
            "turnover": turnover or "Not found",
            "certifications": certifications,
            "projects": projects or "Not found",
        },
        "eligibility_status": eligibility_status,
        "confidence": confidence,
    }

    file_record["analysis"] = analysis_result
    file_record["analyzed_at"] = datetime.utcnow().isoformat()

    return analysis_result


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.post("/api/auth/register")
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register new user"""
    
    # Check if user exists
    existing = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user_id = generate_user_id()
    role_map = {
        "contractor": UserRole.CONTRACTOR,
        "admin": UserRole.ADMIN,
        "evaluator": UserRole.EVALUATOR,
        "citizen": UserRole.CITIZEN,
    }
    user = User(
        id=user_id,
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        company_name=user_data.company_name,
        role=role_map.get(user_data.role, UserRole.CONTRACTOR)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_access_token(user.id, user.email, user.role.value)
    
    return {
        "status": "success",
        "message": "User registered successfully",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
            "full_name": user.full_name,
            "company_name": user.company_name,
        }
    }


@app.post("/api/auth/login")
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(user.id, user.email, user.role.value)
    
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
            "full_name": user.full_name,
            "company_name": user.company_name
        }
    }


@app.get("/api/auth/me")
async def get_current_user(token: str = None, db: Session = Depends(get_db)):
    """Get current user info"""
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role.value,
        "full_name": user.full_name,
        "company_name": user.company_name
    }


@app.get("/api/admin/users")
async def list_admin_users(token: str = None, db: Session = Depends(get_db)):
    """List all users for the admin control panel."""

    require_roles(token, {"admin"})

    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "status": "success",
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role.value,
                "full_name": user.full_name,
                "company_name": user.company_name,
                "is_active": bool(user.is_active),
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ],
    }


@app.put("/api/auth/profile")
async def update_current_user_profile(
    profile: UserProfileUpdate,
    token: str = None,
    db: Session = Depends(get_db),
):
    """Update current user profile details."""

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    duplicate = db.query(User).filter(
        User.id != user.id,
        ((User.email == profile.email) | (User.username == profile.username))
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Email or username already in use")

    user.full_name = profile.full_name.strip()
    user.username = profile.username.strip()
    user.email = profile.email.strip()
    user.company_name = (profile.company_name or "").strip() or None

    db.commit()
    db.refresh(user)

    return {
        "status": "success",
        "message": "Profile updated successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
            "full_name": user.full_name,
            "company_name": user.company_name,
        }
    }


# ============================================================================
# TENDER ENDPOINTS
# ============================================================================

@app.post("/api/tenders/create")
async def create_tender(
    title: str = Form(None),
    description: str = Form(None),
    department: str = Form(None),
    duration_days: int = Form(None),
    investment_amount: str = Form(None),
    penalty_per_day: str = Form(None),
    penalty_max_days: int = Form(180),
    work_location: str = Form(None),
    application_deadline: str = Form(None),
    sector: str = Form("Infrastructure"),
    file: UploadFile = File(...),
    token: str = None,
    db: Session = Depends(get_db)
):
    """Create new tender (Admin only)"""

    token_data = require_roles(token, {"admin"})
    
    try:
        if Path(file.filename or "").suffix.lower() not in {".pdf", ".docx"}:
            raise HTTPException(status_code=400, detail="Tender document must be PDF or DOCX")

        tender_id = str(uuid.uuid4())
        upload_dir = "uploads/tenders"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, f"{tender_id}_{file.filename}")
        with open(file_path, 'wb') as f:
            f.write(await file.read())
        
        tender = Tender(
            id=tender_id,
            title=title or "Untitled Tender",
            description=description or "",
            department=department or "Procurement Department",
            created_by=token_data.user_id,
            document_path=file_path,
            status="active",
            duration_days=duration_days,
            investment_amount=investment_amount,
            penalty_per_day=penalty_per_day,
            penalty_max_days=penalty_max_days or 180,
            work_location=work_location,
            application_deadline=parse_optional_datetime(application_deadline),
            sector=sector or classify_citizen_dashboard_sector(Tender(title=title, description=description, department=department)),
            last_updated=datetime.utcnow(),
        )
        
        db.add(tender)
        db.commit()
        db.refresh(tender)
        
        return {
            "status": "success",
            "message": "Tender created successfully",
            "tender": {
                "id": tender.id,
                "title": tender.title,
                "created_at": tender.created_at.isoformat()
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/tenders")
async def list_tenders(token: str = None, db: Session = Depends(get_db)):
    """List tenders. Admins see every lifecycle state; contractors see open/closed tenders."""
    token_data = require_auth(token)
    query = db.query(Tender).order_by(Tender.created_at.desc())
    if token_data.role != "admin":
        query = query.filter(Tender.status.in_(["active", "closed", "published"]))
    tenders = query.all()
    
    return {
        "status": "success",
        "tenders": [serialize_tender(t, db) for t in tenders]
    }


@app.post("/api/tenders/{tender_id}/update")
async def update_tender(
    tender_id: str,
    title: str = Form(None),
    description: str = Form(None),
    department: str = Form(None),
    duration_days: int = Form(None),
    investment_amount: str = Form(None),
    penalty_per_day: str = Form(None),
    penalty_max_days: int = Form(None),
    work_location: str = Form(None),
    application_deadline: str = Form(None),
    sector: str = Form(None),
    token: str = None,
    db: Session = Depends(get_db),
):
    require_roles(token, {"admin"})
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    if title is not None:
        tender.title = title
    if description is not None:
        tender.description = description
    if department is not None:
        tender.department = department or "Procurement Department"
    if duration_days is not None:
        tender.duration_days = duration_days
    if investment_amount is not None:
        tender.investment_amount = investment_amount
    if penalty_per_day is not None:
        tender.penalty_per_day = penalty_per_day
    if penalty_max_days is not None:
        tender.penalty_max_days = penalty_max_days or 180
    if work_location is not None:
        tender.work_location = work_location
    if application_deadline:
        tender.application_deadline = parse_optional_datetime(application_deadline)
    if sector:
        tender.sector = sector
    
    tender.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(tender)
    return {"status": "success", "tender": serialize_tender(tender, db)}


def _award_tender_to_winner(tender: Tender, winner_eval: Evaluation, db: Session):
    """Internal helper to assign tender and award points to the winning contractor."""
    submission = db.query(BidderSubmission).filter(BidderSubmission.id == winner_eval.submission_id).first()
    if submission:
        user = db.query(User).filter(User.id == submission.bidder_id).first()
        if user:
            user.total_projects = (user.total_projects or 0) + 1
            user.merit_points = (user.merit_points or 0.0) + 50.0
            tender.awarded_to = user.company_name or user.full_name
            return
    tender.awarded_to = winner_eval.bidder_name


@app.post("/api/tenders/{tender_id}/close")
async def close_tender(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    require_roles(token, {"admin"})
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    evaluations = db.query(Evaluation).filter(Evaluation.tender_id == tender_id).order_by(Evaluation.confidence.desc()).all()
    
    if evaluations:
        eligible_evals = [ev for ev in evaluations if ev.decision == "ELIGIBLE"]
        candidates = eligible_evals if eligible_evals else evaluations
        top_score = candidates[0].confidence
        tied_candidates = [ev for ev in candidates if ev.confidence == top_score]
        
        if len(tied_candidates) == 1:
            winner = tied_candidates[0]
            tender.status = "published"
            _award_tender_to_winner(tender, winner, db)
            tender.awarded_at = datetime.utcnow()
            tender.application_deadline = tender.application_deadline or datetime.utcnow()
            tender.last_updated = datetime.utcnow()
            
            audit_logger.log_event(
                tender_id=tender.id,
                action="TENDER_AUTO_AWARDED",
                actor_id=winner.bidder_name,
                details=f"System automatically awarded to highest score: {top_score:.2f}",
                confidence_score=top_score
            )
            db.commit()
            return {"status": "success", "message": f"Tender closed and automatically awarded to {winner.bidder_name}"}
        else:
            tender.status = "closed"
            tender.application_deadline = tender.application_deadline or datetime.utcnow()
            tender.last_updated = datetime.utcnow()
            audit_logger.log_event(
                tender_id=tender.id,
                action="TENDER_CLOSED_TIE",
                actor_id="admin",
                details=f"Tender closed but a tie was found among {len(tied_candidates)} top bidders."
            )
            db.commit()
            return {"status": "tie", "message": f"Tender closed. Tie detected among {len(tied_candidates)} bidders. Manual award required."}

    tender.status = "closed"
    tender.application_deadline = tender.application_deadline or datetime.utcnow()
    tender.last_updated = datetime.utcnow()
    db.commit()
    return {"status": "success", "message": "Tender application closed"}


@app.post("/api/tenders/{tender_id}/reopen")
async def reopen_tender(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    require_roles(token, {"admin"})
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.status not in {"closed", "published"}:
        raise HTTPException(status_code=400, detail="Only closed or published tenders can be reopened")

    if tender.status in {"closed", "published"}:
        tender.awarded_to = None
        tender.awarded_at = None
        
        # Delete existing evaluations so they must be run again
        db.query(Evaluation).filter(Evaluation.tender_id == tender_id).delete()

    tender.status = "active"
    if not tender.application_deadline or tender.application_deadline <= datetime.utcnow():
        tender.application_deadline = datetime.utcnow() + timedelta(days=7)
    tender.last_updated = datetime.utcnow()
    audit_logger.log_event(
        tender_id=tender.id,
        action="TENDER_REOPENED",
        actor_id="admin",
        details="Tender application period reopened. Existing evaluations cleared."
    )
    db.commit()
    return {
        "status": "success",
        "message": "Tender reopened for applications",
        "application_deadline": tender.application_deadline.isoformat() if tender.application_deadline else None,
    }


@app.post("/api/tenders/{tender_id}/publish")
async def publish_tender(tender_id: str, token: str = None, manual_winner: str = None, db: Session = Depends(get_db)):
    require_roles(token, {"admin"})
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.status != "closed" and not manual_winner:
        raise HTTPException(status_code=400, detail="Close the application before publishing results")

    evaluations = (
        db.query(Evaluation)
        .filter(Evaluation.tender_id == tender_id)
        .order_by(Evaluation.confidence.desc(), Evaluation.evaluated_at.asc())
        .all()
    )
    if not evaluations:
        raise HTTPException(status_code=400, detail="No evaluated submissions to publish")

    if manual_winner:
        winner = next((ev for ev in evaluations if ev.bidder_name == manual_winner), None)
        if not winner:
            raise HTTPException(status_code=400, detail="Provided manual winner not found in evaluations")
    else:
        eligible_evals = [ev for ev in evaluations if ev.decision == "ELIGIBLE"]
        candidates = eligible_evals if eligible_evals else evaluations
        top_score = candidates[0].confidence
        tied_candidates = [ev for ev in candidates if ev.confidence == top_score]
        if len(tied_candidates) > 1:
            raise HTTPException(status_code=400, detail="Tie detected. Must provide manual_winner to publish.")
        winner = candidates[0]

    tender.status = "published"
    _award_tender_to_winner(tender, winner, db)
    tender.awarded_at = datetime.utcnow()
    tender.last_updated = datetime.utcnow()
    
    audit_logger.log_event(
        tender_id=tender.id,
        action="TENDER_AWARDED_MANUAL" if manual_winner else "TENDER_AWARDED_AUTO",
        actor_id="admin",
        details=f"Tender awarded to {winner.bidder_name}." + (f" (Manual selection: {manual_winner})" if manual_winner else ""),
        confidence_score=winner.confidence
    )
    
    db.commit()

    return {
        "status": "success",
        "message": "Tender result published",
        "winner": winner.bidder_name,
    }


@app.post("/api/tenders/{tender_id}/recall")
async def recall_tender_result(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    require_roles(token, {"admin"})
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.status != "published":
        raise HTTPException(status_code=400, detail="Only published tenders can be recalled")

    tender.status = "closed"
    tender.awarded_to = None
    tender.awarded_at = None
    tender.last_updated = datetime.utcnow()
    
    audit_logger.log_event(
        tender_id=tender.id,
        action="TENDER_RESULT_RECALLED",
        actor_id="admin",
        details="Published tender results have been recalled. Tender moved back to closed state."
    )
    
    db.commit()

    return {"status": "success", "message": "Published result recalled"}


@app.get("/api/tenders/{tender_id}")
async def get_tender(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    """Get tender details"""
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    submissions = db.query(BidderSubmission).filter(
        BidderSubmission.tender_id == tender_id
    ).all()
    
    evaluations = db.query(Evaluation).filter(
        Evaluation.tender_id == tender_id
    ).all()
    
    return {
        "status": "success",
        "tender": {
            "id": tender.id,
            "title": tender.title,
            "description": tender.description,
            "created_at": tender.created_at.isoformat(),
            "submissions_count": len(submissions),
            "evaluations_count": len(evaluations),
            "status": tender.status
        }
    }


@app.get("/api/tenders/{tender_id}/timeline")
async def get_tender_timeline(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    """Get tender lifecycle timeline."""
    token_data = require_auth(token)
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    if token_data.role == "citizen" and (tender.status or "").lower() not in PUBLISHED_STATUSES:
        raise HTTPException(status_code=403, detail="Timeline is available only after publication")

    return {
        "status": "success",
        "tender_id": tender.id,
        "title": tender.title,
        "timeline": build_tender_timeline(db, tender, token_data),
    }


# ============================================================================
# SUBMISSION ENDPOINTS
# ============================================================================

@app.post("/api/submissions/submit")
async def submit_bidder(
    tender_id: str = Form(...),
    bidder_name: str = Form(...),
    company_name: str = Form(...),
    file: UploadFile = File(...),
    token: str = None,
    db: Session = Depends(get_db)
):
    """Submit bidder document"""
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        # Check tender exists
        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")
        if tender.status != "active":
            raise HTTPException(status_code=400, detail="Tender is not open for applications")
        if tender.application_deadline and datetime.utcnow() > tender.application_deadline:
            raise HTTPException(status_code=400, detail="Tender application date is closed")
        if Path(file.filename or "").suffix.lower() not in {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff"}:
            raise HTTPException(status_code=400, detail="Submission must be PDF, DOCX, or an image")
        
        # Save submission document
        submission_id = str(uuid.uuid4())
        upload_dir = "uploads/submissions"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, f"{submission_id}_{file.filename}")
        with open(file_path, 'wb') as f:
            f.write(await file.read())
        
        # Create submission record
        submission = BidderSubmission(
            id=submission_id,
            tender_id=tender_id,
            bidder_id=token_data.user_id,
            bidder_name=bidder_name,
            company_name=company_name,
            document_path=file_path,
            status="submitted"
        )
        
        db.add(submission)
        db.commit()
        db.refresh(submission)
        
        # Auto-evaluate
        evaluation_result = await _evaluate_submission(
            tender, submission, file_path, db, token_data.user_id
        )
        
        return {
            "status": "success",
            "message": "Submission received. Results will be visible after admin review and publishing.",
            "submission": {
                "id": submission.id,
                "tender_id": tender_id,
                "bidder_name": bidder_name,
                "submitted_at": submission.submitted_at.isoformat()
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/submissions/{tender_id}")
async def list_submissions(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    """List submissions for tender"""
    token_data = require_auth(token)
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    submissions_query = db.query(BidderSubmission).filter(BidderSubmission.tender_id == tender_id)
    if token_data.role != "admin":
        submissions_query = submissions_query.filter(BidderSubmission.bidder_id == token_data.user_id)
    submissions = submissions_query.all()
    
    result = []
    for sub in submissions:
        evaluation = db.query(Evaluation).filter(
            Evaluation.submission_id == sub.id
        ).first()
        can_show_result = token_data.role == "admin" or tender_is_published(tender)
        result.append({
            "id": sub.id,
            "bidder_name": sub.bidder_name,
            "company_name": sub.company_name,
            "submitted_at": sub.submitted_at.isoformat(),
            "status": sub.status,
            "document_path": sub.document_path,
            "evaluation": {
                "decision": evaluation.decision if evaluation else "pending",
            } if evaluation and can_show_result else None
        })
    
    return {
        "status": "success",
        "submissions": result
    }

@app.get("/api/submissions/document/{submission_id}")
async def get_submission_document(submission_id: str, token: str = None, db: Session = Depends(get_db)):
    """Serve submitted bidder document"""
    token_data = require_auth(token)
    submission = db.query(BidderSubmission).filter(BidderSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Check access: admin or the bidder themselves
    if token_data.role != "admin" and submission.bidder_id != token_data.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not submission.document_path or not os.path.exists(submission.document_path):
        raise HTTPException(status_code=404, detail="Document file not found")
        
    return FileResponse(submission.document_path)


# ============================================================================
# EVALUATION ENDPOINTS
# ============================================================================

@app.get("/api/evaluations/{tender_id}")
async def list_evaluations(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    """List evaluations for tender"""
    token_data = require_auth(token)
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    evaluation_query = db.query(Evaluation).filter(Evaluation.tender_id == tender_id)
    if token_data.role != "admin":
        if not tender_is_published(tender):
            return {"status": "success", "evaluations": []}
        submission_ids = [
            row.id for row in db.query(BidderSubmission.id).filter(
                BidderSubmission.tender_id == tender_id,
                BidderSubmission.bidder_id == token_data.user_id,
            ).all()
        ]
        evaluation_query = evaluation_query.filter(Evaluation.submission_id.in_(submission_ids))

    evaluations = evaluation_query.all()
    
    return {
        "status": "success",
        "evaluations": [
            {
                "id": e.id,
                "submission_id": e.submission_id,
                "bidder_name": e.bidder_name,
                "decision": e.decision,
                "confidence": e.confidence,
                "evaluated_at": e.evaluated_at.isoformat(),
                "audit_id": e.audit_id
            }
            for e in evaluations
        ]
    }


@app.get("/api/evaluations/detail/{evaluation_id}")
async def get_evaluation_detail(evaluation_id: str, token: str = None, db: Session = Depends(get_db)):
    """Get detailed evaluation"""
    token_data = require_auth(token)
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    tender = db.query(Tender).filter(Tender.id == evaluation.tender_id).first()
    if token_data.role != "admin":
        submission = db.query(BidderSubmission).filter(BidderSubmission.id == evaluation.submission_id).first()
        if not tender or not tender_is_published(tender) or not submission or submission.bidder_id != token_data.user_id:
            raise HTTPException(status_code=403, detail="Result is not published yet")
    
    criteria_breakdown = json.loads(evaluation.criteria_breakdown) if evaluation.criteria_breakdown else {}
    summary = evaluation.summary
    if token_data.role != "admin":
        criteria_breakdown = [
            {key: value for key, value in item.items() if key != "confidence"}
            for item in criteria_breakdown
        ] if isinstance(criteria_breakdown, list) else criteria_breakdown
        summary_lines = [
            line for line in (summary or "").splitlines()
            if "confidence" not in line.lower() and "smart tender score" not in line.lower()
        ]
        summary = "\n".join(summary_lines)
    
    return {
        "status": "success",
        "evaluation": {
            "id": evaluation.id,
            "bidder_name": evaluation.bidder_name,
            "decision": evaluation.decision,
            "summary": summary,
            "criteria_breakdown": criteria_breakdown,
            "evaluated_at": evaluation.evaluated_at.isoformat(),
            "audit_id": evaluation.audit_id
        }
    }


from pydantic import BaseModel
import google.generativeai as genai

class AIAnalysisRequest(BaseModel):
    model: str
    st_weight: float = 4.0
    sob_weight: float = 3.0
    sp_weight: float = 3.0

@app.post("/api/evaluations/{tender_id}/ai-analysis")
async def ai_analysis(tender_id: str, request: AIAnalysisRequest, token: str = None, db: Session = Depends(get_db)):
    """Run AI analysis on tender evaluations with custom weights"""
    token_data = require_roles(token, {"admin"})
    
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    evaluations = db.query(Evaluation).filter(Evaluation.tender_id == tender_id).all()
    if not evaluations:
        raise HTTPException(status_code=404, detail="No evaluations found for this tender")
        
    summary_text = f"Tender: {tender.title}\n"
    summary_text += f"Budget: {tender.investment_amount}, Target Duration: {tender.duration_days} days\n"
    summary_text += f"Requirements: {tender.description}\n\n"
    
    for ev in evaluations:
        # Fetch submission to get more data if available
        sub = db.query(BidderSubmission).filter(BidderSubmission.id == ev.submission_id).first()
        summary_text += f"--- Bidder: {ev.bidder_name} ---\n"
        summary_text += f"AI Decision: {ev.decision}, Confidence: {ev.confidence}\n"
        summary_text += f"AI Summary: {ev.summary}\n"
        if sub:
            summary_text += f"Submission Status: {sub.status}\n"
        summary_text += "\n"
        
    prompt = f"""You are the evaluation engine for Project Antigravity. 
Analyze the provided tender data and bidder evaluations. 
Provide a detailed score out of {request.st_weight + request.sob_weight + request.sp_weight} based on these CUSTOM WEIGHTS provided by the Admin:

1. ST (Tender Match Score): Max {request.st_weight}
   - Evaluate alignment with technical & commercial requirements.
   - Consider PRICE and PROPOSED DURATION relative to tender budget and target timeline.

2. SOB (Order Book Score): Max {request.sob_weight}
   - Evaluate pipeline health and capacity to take on this project.

3. SP (Performance Score): Max {request.sp_weight}
   - Evaluate historical execution and quality based on the AI summaries.

For each bidder:
- Calculate individual scores (ST, SOB, SP) with decimal precision.
- Provide a clear justification for each score, specifically emphasizing Price and Duration alignment for ST.
- Calculate the Total Score.

Finally, announce the ranking:
- WINNER (Rank 1)
- 1st RUNNER-UP (Rank 2 - if available)
- 2nd RUNNER-UP (Rank 3 - if available)

If there are fewer than 3 bidders, simply rank all available participants. If there is only one bidder, evaluate their performance against the tender baseline.

Maintain extreme transparency and strictly adhere to the max caps for each category.

Tender & Evaluations Data:
{summary_text}
"""
    
    if request.model == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
        
        try:
            genai.configure(api_key=api_key)
            # Using Gemini 2.5 Flash as requested
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            return {"status": "success", "analysis": response.text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")
    elif request.model in ["sarvam", "claude", "chatgpt"]:
        # Mocking for others
        return {"status": "success", "analysis": f"[{request.model.capitalize()} API key pending configuration]. \n\nMock Analysis: The evaluations look consistent. {len(evaluations)} bids were processed."}
    else:
        raise HTTPException(status_code=400, detail="Invalid model selected")



@app.post("/api/evaluations/{evaluation_id}/override")
async def override_evaluation(
    evaluation_id: str,
    override_data: OverrideRequest,
    token: str = None,
    db: Session = Depends(get_db)
):
    """Override evaluation decision"""
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data or token_data.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    # Create override record
    override = Override(
        id=str(uuid.uuid4()),
        evaluation_id=evaluation_id,
        original_decision=evaluation.decision,
        new_decision=override_data.new_decision,
        reason=override_data.reason,
        overridden_by=token_data.user_id
    )
    
    # Update evaluation
    evaluation.decision = override_data.new_decision
    
    db.add(override)
    db.commit()
    
    return {
        "status": "success",
        "message": "Decision overridden successfully",
        "override": {
            "id": override.id,
            "original_decision": override.original_decision,
            "new_decision": override.new_decision,
            "overridden_at": override.overridden_at.isoformat()
        }
    }


# ============================================================================
# SUPPORT TICKET ENDPOINTS
# ============================================================================

@app.post("/api/support/tickets", response_model=TicketResponse)
async def create_ticket(ticket_data: TicketCreate, token: str = None, db: Session = Depends(get_db)):
    """Create a new support ticket"""
    token_data = require_auth(token)
    user = db.query(User).filter(User.id == token_data.user_id).first()
    
    ticket = SupportTicket(
        id=str(uuid.uuid4()),
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        subject=ticket_data.subject,
        message=ticket_data.message,
        priority=ticket_data.priority,
        status="active"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    # Add dummy replies field for response model
    ticket.replies = []
    return ticket


@app.get("/api/support/tickets", response_model=List[TicketResponse])
async def list_tickets(token: str = None, db: Session = Depends(get_db)):
    """List support tickets (role-filtered)"""
    token_data = require_auth(token)
    
    if token_data.role == "admin":
        # Admin sees all non-resolved tickets
        tickets = db.query(SupportTicket).filter(SupportTicket.status != "resolved").order_by(SupportTicket.created_at.desc()).all()
    else:
        # Others see only their own tickets
        tickets = db.query(SupportTicket).filter(SupportTicket.user_id == token_data.user_id).order_by(SupportTicket.created_at.desc()).all()
    
    for ticket in tickets:
        ticket.replies = db.query(TicketReply).filter(TicketReply.ticket_id == ticket.id).order_by(TicketReply.sent_at.asc()).all()
    
    return tickets


@app.post("/api/support/tickets/{ticket_id}/reply", response_model=TicketReplyResponse)
async def reply_to_ticket(ticket_id: str, reply_data: TicketReplyCreate, token: str = None, db: Session = Depends(get_db)):
    """Reply to a support ticket"""
    token_data = require_auth(token)
    
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    reply = TicketReply(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        user_id=token_data.user_id,
        message=reply_data.message
    )
    
    # Update ticket status
    if token_data.role == "admin":
        ticket.status = "replied"
    else:
        ticket.status = "active"
        ticket.is_read = False # Mark as unread for admin if user replies
        
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


@app.post("/api/support/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, token: str = None, db: Session = Depends(get_db)):
    """Mark a ticket as resolved"""
    require_roles(token, {"admin"})
    
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.status = "resolved"
    db.commit()
    return {"status": "success", "message": "Ticket resolved"}


@app.post("/api/support/tickets/{ticket_id}/read")
async def mark_ticket_read(ticket_id: str, token: str = None, db: Session = Depends(get_db)):
    """Mark a ticket as read"""
    token_data = require_auth(token)
    
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    if token_data.role == "admin":
        ticket.is_read = True
        db.commit()
        
    return {"status": "success"}


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(token: str = None, db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    require_auth(token)
    
    total_tenders = db.query(Tender).count()
    active_tenders = db.query(Tender).filter(Tender.status == "active").count()
    total_submissions = db.query(BidderSubmission).count()
    
    evaluations = db.query(Evaluation).all()
    pending_evaluations = db.query(BidderSubmission).filter(
        BidderSubmission.status == "submitted"
    ).count()
    
    approved = sum(1 for e in evaluations if e.decision == "ELIGIBLE")
    rejected = sum(1 for e in evaluations if e.decision == "NOT_ELIGIBLE")
    
    return {
        "status": "success",
        "stats": {
            "total_tenders": total_tenders,
            "active_tenders": active_tenders,
            "total_submissions": total_submissions,
            "pending_evaluations": pending_evaluations,
            "approved_bidders": approved,
            "rejected_bidders": rejected
        }
    }


@app.get("/api/admin/contractor-stats")
async def admin_contractor_stats(token: str = None, db: Session = Depends(get_db)):
    """Retrieve performance metrics for all contractors."""
    require_roles(token, {"admin"})
    
    contractors = db.query(User).filter(User.role == UserRole.CONTRACTOR).all()
    
    results = []
    for c in contractors:
        # Avoid division by zero
        success_rate = (c.on_time_completions / c.total_projects * 100) if (c.total_projects or 0) > 0 else 0
        results.append({
            "id": c.id,
            "full_name": c.full_name,
            "company_name": c.company_name or "Individual",
            "merit_points": c.merit_points or 0.0,
            "demerit_points": c.demerit_points or 0.0,
            "on_time_completions": c.on_time_completions or 0,
            "total_projects": c.total_projects or 0,
            "success_rate": round(success_rate, 1)
        })
        
    return {"status": "success", "stats": results}


@app.post("/api/admin/delete-user")
async def delete_user(user_id: str, token: str = None, db: Session = Depends(get_db)):
    """Delete a user and their associated data."""
    require_roles(token, {"admin"})
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Optional: Delete associated submissions/logs if needed
    db.delete(user)
    db.commit()
    return {"status": "success", "message": "User deleted"}


@app.get("/api/dashboard/admin/analytics")
async def get_admin_analytics(token: str = None, db: Session = Depends(get_db)):
    """Get admin analytics"""
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data or token_data.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total_users = db.query(User).count()
    contractors = db.query(User).filter(User.role == UserRole.CONTRACTOR).count()
    admins = db.query(User).filter(User.role == UserRole.ADMIN).count()
    
    total_tenders = db.query(Tender).count()
    total_evaluations = db.query(Evaluation).count()
    
    evaluations = db.query(Evaluation).all()
    avg_confidence = sum(e.confidence for e in evaluations) / len(evaluations) if evaluations else 0
    
    manual_review = sum(1 for e in evaluations if e.decision == "MANUAL_REVIEW")
    manual_review_rate = (manual_review / len(evaluations) * 100) if evaluations else 0
    
    return {
        "status": "success",
        "analytics": {
            "total_users": total_users,
            "contractors": contractors,
            "admins": admins,
            "total_tenders": total_tenders,
            "total_evaluations": total_evaluations,
            "average_confidence": f"{avg_confidence:.0%}",
            "manual_review_rate": f"{manual_review_rate:.1f}%"
        }
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _evaluate_submission(tender, submission, file_path, db, user_id):
    """Evaluate bidder submission"""
    
    try:
        # Get tender document
        result = evaluator.evaluate_bidder(
            tender_doc_path=tender.document_path,
            bidder_doc_path=file_path,
            bidder_name=submission.bidder_name,
            tender_id=tender.id
        )
        bidder_text, _, _ = evaluator.doc_processor.process_document(file_path)
        proposal = extract_proposal_insights(bidder_text)
        smart_score = calculate_smart_score(result.overall_confidence, tender, proposal)
        proposal_rows = [
            {
                "criterion_id": "SMART_001",
                "criterion_name": "Proposal Amount",
                "status": "EXTRACTED" if proposal["amount_rupees"] else "NOT_FOUND",
                "confidence": 0.85 if proposal["amount_rupees"] else 0.2,
                "reason": proposal["amount_text"],
            },
            {
                "criterion_id": "SMART_002",
                "criterion_name": "Completion Timeline",
                "status": "EXTRACTED" if proposal["completion_days"] else "NOT_FOUND",
                "confidence": 0.85 if proposal["completion_days"] else 0.2,
                "reason": proposal["completion_text"],
            },
            {
                "criterion_id": "SMART_003",
                "criterion_name": "Smart Tender Score",
                "status": "SCORED",
                "confidence": smart_score,
                "reason": "Weighted score from eligibility, quoted amount, and delivery speed",
            },
        ]
        summary = (
            f"{result.summary}\n"
            f"Proposal: {proposal['proposal_summary']}\n"
            f"Smart tender score: {smart_score:.0%}"
        )
        
        # Save evaluation
        evaluation = Evaluation(
            id=str(uuid.uuid4()),
            tender_id=tender.id,
            submission_id=submission.id,
            bidder_name=submission.bidder_name,
            decision=result.final_decision.value,
            confidence=smart_score,
            summary=summary,
            criteria_breakdown=json.dumps([
                {
                    "criterion_id": c.criterion_id,
                    "criterion_name": c.criterion_name,
                    "status": c.status.value,
                    "confidence": c.confidence,
                    "reason": c.reason
                }
                for c in result.criterion_evaluations
            ] + proposal_rows),
            evaluated_by=user_id,
            audit_id=result.audit_id
        )
        
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        
        return evaluation
    
    except Exception as e:
        print(f"Evaluation error: {e}")
        raise



# ============================================================================
# CITIZEN PUBLIC PORTAL ENDPOINTS
# ============================================================================

@app.get("/api/public/awarded-tenders")
async def get_awarded_tenders(token: str = None, db: Session = Depends(get_db)):
    """Public endpoint — awarded tenders with top 3 bidders (Citizen view)"""

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Get all tenders that have at least one ELIGIBLE evaluation
    tenders = db.query(Tender).all()
    result = []

    for tender in tenders:
        if not tender_is_published(tender):
            continue
        # Get all ELIGIBLE evaluations for this tender, sorted by confidence desc
        eligible = (
            db.query(Evaluation)
            .filter(
                Evaluation.tender_id == tender.id,
                Evaluation.decision == "ELIGIBLE"
            )
            .order_by(Evaluation.confidence.desc())
            .all()
        )

        if not eligible:
            continue

        # Build top-3 list
        top3 = []
        ranks = ["🥇 Winner", "🥈 Runner-up", "🥉 2nd Runner-up"]
        for i, ev in enumerate(eligible[:3]):
            top3.append({
                "rank": i + 1,
                "rank_label": ranks[i],
                "bidder_name": ev.bidder_name,
                "confidence_score": f"{ev.confidence:.0%}",
            })

        # Penalty info
        max_days = tender.penalty_max_days or 180
        penalty_info = None
        if tender.penalty_per_day:
            penalty_info = {
                "rate": tender.penalty_per_day,
                "max_days": max_days,
                "applies": True,
                "note": f"Penalty of {tender.penalty_per_day} applies for delays up to {max_days} days"
            }
        else:
            penalty_info = {
                "applies": False,
                "note": "No penalty clause specified"
            }

        result.append({
            "tender_id": tender.id,
            "title": tender.title,
            "description": tender.description,
            "status": tender.status,
            "created_at": tender.created_at.isoformat(),
            "work_location": tender.work_location or "Not specified",
            "duration_days": tender.duration_days,
            "duration_label": f"{tender.duration_days} days" if tender.duration_days else "Not specified",
            "investment": tender.investment_amount or "Not disclosed",
            "total_bidders": db.query(Evaluation).filter(Evaluation.tender_id == tender.id).count(),
            "eligible_bidders": len(eligible),
            "top3": top3,
            "penalty": penalty_info,
        })

    return {"status": "success", "tenders": result}


@app.get("/api/public/tender/{tender_id}")
async def get_public_tender_detail(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    """Public detail view for a single tender (Citizen)"""

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if not tender_is_published(tender):
        raise HTTPException(status_code=403, detail="Tender result is not published yet")

    all_evals = (
        db.query(Evaluation)
        .filter(Evaluation.tender_id == tender_id)
        .order_by(Evaluation.confidence.desc())
        .all()
    )

    eligible = [e for e in all_evals if e.decision == "ELIGIBLE"]
    not_eligible = [e for e in all_evals if e.decision == "NOT_ELIGIBLE"]
    review = [e for e in all_evals if e.decision == "MANUAL_REVIEW"]

    ranks = ["🥇 Winner", "🥈 Runner-up", "🥉 2nd Runner-up"]
    top3 = [
        {
            "rank": i + 1,
            "rank_label": ranks[i],
            "bidder_name": ev.bidder_name,
            "confidence_score": f"{ev.confidence:.0%}",
            "evaluated_at": ev.evaluated_at.isoformat(),
        }
        for i, ev in enumerate(eligible[:3])
    ]

    max_days = tender.penalty_max_days or 180

    return {
        "status": "success",
        "tender": {
            "id": tender.id,
            "title": tender.title,
            "description": tender.description,
            "status": tender.status,
            "created_at": tender.created_at.isoformat(),
            "work_location": tender.work_location or "Not specified",
            "duration_days": tender.duration_days,
            "duration_label": f"{tender.duration_days} days" if tender.duration_days else "Not specified",
            "investment": tender.investment_amount or "Not disclosed",
            "penalty": {
                "applies": bool(tender.penalty_per_day),
                "rate": tender.penalty_per_day or "N/A",
                "max_days": max_days,
                "note": (
                    f"Penalty of {tender.penalty_per_day} per day for delays up to {max_days} days"
                    if tender.penalty_per_day
                    else "No penalty clause specified"
                )
            },
            "stats": {
                "total_bidders": len(all_evals),
                "eligible": len(eligible),
                "not_eligible": len(not_eligible),
                "manual_review": len(review),
            },
            "top3": top3,
        }
    }


@app.get("/api/contractor/history")
async def contractor_history(token: str = None, db: Session = Depends(get_db)):
    token_data = require_roles(token, {"contractor"})
    submissions = (
        db.query(BidderSubmission)
        .filter(BidderSubmission.bidder_id == token_data.user_id)
        .order_by(BidderSubmission.submitted_at.desc())
        .all()
    )

    items = []
    for sub in submissions:
        tender = db.query(Tender).filter(Tender.id == sub.tender_id).first()
        evaluation = db.query(Evaluation).filter(Evaluation.submission_id == sub.id).first()
        published = bool(tender and tender_is_published(tender))
        is_winner = bool(published and tender.awarded_to == sub.bidder_name)
        items.append({
            "submission_id": sub.id,
            "tender_id": sub.tender_id,
            "tender_title": tender.title if tender else "Deleted tender",
            "tender_status": tender.status if tender else "unknown",
            "bidder_name": sub.bidder_name,
            "company_name": sub.company_name,
            "submitted_at": sub.submitted_at.isoformat(),
            "result_status": (
                "Winner" if is_winner else
                (evaluation.decision.replace("_", " ").title() if published and evaluation else "Under admin review")
            ),
            "published": published,
            "published_at": tender.awarded_at.isoformat() if published and tender.awarded_at else None,
        })

    return {"status": "success", "history": items}


@app.get("/api/contractor/orderbook")
async def contractor_orderbook(token: str = None, db: Session = Depends(get_db)):
    """List tenders awarded to the current contractor."""
    token_data = require_roles(token, {"contractor"})
    
    # In this system, 'awarded_to' stores the bidder_name of the winner.
    # We find tenders where the status is 'published' and the awarded_to matches 
    # the contractor's name/full_name.
    
    # First, get the bidder name used by this contractor in their submissions
    # or just use their full_name/username as stored in the system.
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Match by company_name or full_name
    tenders = (
        db.query(Tender)
        .filter(Tender.status == "published")
        .filter((Tender.awarded_to == user.company_name) | (Tender.awarded_to == user.full_name))
        .order_by(Tender.awarded_at.desc())
        .all()
    )

    return {
        "status": "success",
        "orderbook": [serialize_tender(t, db) for t in tenders]
    }


@app.get("/api/citizen/tenders")
async def get_citizen_tenders(token: str = None, db: Session = Depends(get_db)):
    """Citizen-safe list of finalized or post-award tenders."""
    require_roles(token, {"citizen", "admin", "evaluator"})
    tenders = list_public_tenders(db)
    return {
        "status": "success",
        "tenders": [item.model_dump() for item in tenders],
    }


@app.get("/api/citizen/tender/{tender_id}")
async def get_citizen_tender_detail(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    """Citizen-safe tender detail without raw internal evaluation data."""
    require_roles(token, {"citizen", "admin", "evaluator"})
    try:
        detail = build_citizen_tender_detail(db, tender_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tender not found")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {
        "status": "success",
        "tender": detail.model_dump(mode="json"),
    }


@app.get("/api/citizen/tender/{tender_id}/explanation")
async def get_citizen_tender_explanation(tender_id: str, token: str = None, db: Session = Depends(get_db)):
    """Simplified public explanation for why the bidder won."""
    require_roles(token, {"citizen", "admin", "evaluator"})
    try:
        explanation = build_citizen_tender_explanation(db, tender_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tender not found")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {
        "status": "success",
        "explanation": explanation.model_dump(),
    }


@app.get("/api/citizen/sectors")
async def get_citizen_sectors(token: str = None, db: Session = Depends(get_db)):
    """Dynamic sector-wise analytics for the citizen dashboard."""
    require_roles(token, {"citizen", "admin", "evaluator"})
    
    tenders = db.query(Tender).all()
    published = [t for t in tenders if (t.status or "").lower() in PUBLISHED_STATUSES]
    
    total_count = len(published)
    if total_count == 0:
        return {"status": "success", "sectors": []}
        
    counts = {}
    descriptions = {
        "Infrastructure": "Roads, construction, water supply",
        "TECH": "Manpower, digital systems, hardware, service delivery",
        "Education": "School development, devices, books, uniforms, nutrition support",
        "Agriculture": "Watershed, farming equipment",
        "Insurance": "Mediclaim policies",
        "General": "Other miscellaneous tenders"
    }
    
    for t in published:
        s = classify_citizen_dashboard_sector(t)
        counts[s] = counts.get(s, 0) + 1
        
    sectors = []
    for s, count in counts.items():
        sectors.append({
            "sector": s,
            "percentage": round((count / total_count) * 100),
            "tender_count": count,
            "description": descriptions.get(s, f"Procurement related to {s}")
        })
        
    sectors.sort(key=lambda x: x["tender_count"], reverse=True)
    
    return {
        "status": "success",
        "sectors": sectors,
    }


@app.get("/api/citizen/stats")
async def get_citizen_stats(
    token: str = None,
    sector: str = None,
    department: str = None,
    tender_status: str = None,
    db: Session = Depends(get_db),
):
    """Citizen-facing filtered amount statistics for published tenders."""
    require_roles(token, {"citizen", "admin", "evaluator"})

    published_tenders = [
        tender for tender in db.query(Tender).order_by(Tender.created_at.desc()).all()
        if (tender.status or "").lower() in PUBLISHED_STATUSES
    ]

    normalized_sector = (sector or "").strip().lower()
    normalized_department = (department or "").strip().lower()
    normalized_status = (tender_status or "").strip().lower()

    decorated = []
    for tender in published_tenders:
        dashboard_sector = classify_citizen_dashboard_sector(tender)
        amount_rupees = parse_money_to_rupees(tender.investment_amount)
        decorated.append({
            "id": tender.id,
            "title": tender.title,
            "department": tender.department or "Procurement Department",
            "status": (tender.status or "published").lower(),
            "sector": dashboard_sector,
            "amount_rupees": amount_rupees,
            "amount_label": tender.investment_amount or "Not disclosed",
        })

    filtered = [
        item for item in decorated
        if (not normalized_sector or item["sector"].lower() == normalized_sector)
        and (not normalized_department or item["department"].lower() == normalized_department)
        and (not normalized_status or item["status"] == normalized_status)
    ]

    numeric_amounts = [item["amount_rupees"] for item in filtered if item["amount_rupees"] is not None]
    total_amount = sum(numeric_amounts) if numeric_amounts else 0
    average_amount = (total_amount / len(numeric_amounts)) if numeric_amounts else 0
    highest_item = max(
        (item for item in filtered if item["amount_rupees"] is not None),
        key=lambda item: item["amount_rupees"],
        default=None,
    )

    return {
        "status": "success",
        "summary": {
            "total_tenders": len(filtered),
            "tenders_with_amount": len(numeric_amounts),
            "total_amount_rupees": round(total_amount, 2),
            "average_amount_rupees": round(average_amount, 2),
            "highest_amount_rupees": round(highest_item["amount_rupees"], 2) if highest_item else 0,
            "highest_amount_tender": highest_item["title"] if highest_item else "No matching tender",
        },
        "filters": {
            "sector": sector or "",
            "department": department or "",
            "tender_status": tender_status or "",
            "available_sectors": sorted({item["sector"] for item in decorated}),
            "available_departments": sorted({item["department"] for item in decorated}),
            "available_statuses": sorted({item["status"] for item in decorated}),
        },
        "breakdown": [
            {
                "tender_id": item["id"],
                "title": item["title"],
                "sector": item["sector"],
                "department": item["department"],
                "status": item["status"],
                "amount": item["amount_label"],
                "amount_rupees": item["amount_rupees"],
            }
            for item in filtered[:25]
        ],
    }


@app.get("/api/citizen/sectors/{sector_name}")
async def get_citizen_sector_detail(sector_name: str, token: str = None, db: Session = Depends(get_db)):
    """Tender list for a selected sector based on real data."""
    require_roles(token, {"citizen", "admin", "evaluator"})

    tenders = db.query(Tender).all()
    published = [t for t in tenders if (t.status or "").lower() in PUBLISHED_STATUSES]
    
    matches = []
    for t in published:
        if classify_citizen_dashboard_sector(t).lower() == sector_name.lower():
            matches.append({
                "tender_id": t.id,
                "title": t.title,
                "department": t.department or "Procurement Department",
                "status": t.status
            })

    if not matches:
        if sector_name.title() not in {"Infrastructure", "TECH", "Education", "Agriculture", "Insurance", "General"}:
             raise HTTPException(status_code=404, detail="Sector not found")

    return {
        "status": "success",
        "sector": sector_name.title(),
        "tenders": matches,
    }


@app.get("/api/audit/all")
async def get_all_audit_logs(token: str = None):
    """Retrieve all audit logs across the system (admin only)"""
    require_roles(token, {"admin"})
    logs = audit_logger.get_all_logs(limit=20)
    return {
        "status": "success",
        "logs": logs
    }



@app.get("/")
async def root():
    """Serve the dashboard"""
    return FileResponse("frontend/index.html")


@app.get("/styles.css")
async def styles():
    return FileResponse("frontend/styles.css")


@app.get("/app.js")
async def app_js():
    return FileResponse("frontend/app.js")


app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
