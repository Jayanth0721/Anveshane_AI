# Anveshane AI 🛡️
### *Empowering Procurement through Intelligence, Transparency, and Auditability*

> **"Bridging the gap between government procurement and public trust — one explainable verdict at a time."**

Anveshane AI is a full-stack, AI-powered procurement evaluation platform built for government tendering. It transforms unstructured bidder documents into structured, evidence-backed evaluation reports — with a public citizen portal, a smart scoring engine, and a legally defensible audit trail baked in from day one.

---

## 📋 Table of Contents

- [The Problem](#-the-problem)
- [The Vision](#-the-vision)
- [Architecture Overview](#-architecture-overview)
- [Core Features — The 19 Pillars](#-core-features--the-19-pillars)
- [AI Evaluation Pipeline](#-ai-evaluation-pipeline)
- [Smart Scoring Formula](#-smart-scoring-formula)
- [Data Models](#-data-models)
- [API Reference](#-api-reference)
- [Technology Stack](#️-technology-stack)
- [Installation & Setup](#️-installation--setup)
- [Usage Guide](#-usage-guide)
- [Test Credentials](#-test-credentials)
- [Audit & Compliance](#-audit--compliance)
- [Citizen Transparency Portal](#-citizen-transparency-portal)
- [Sector Intelligence](#-sector-intelligence)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)

---

## 🚨 The Problem

Government tender evaluation today is:

| Issue | Impact |
|-------|--------|
| **Manual & Slow** | Officers spend days reviewing hundreds of pages per tender |
| **Inconsistent** | Two evaluators reach different verdicts from the same documents |
| **Opaque** | Citizens have zero visibility into who won a tender or why |
| **Hard to Audit** | No traceable trail from decision back to source evidence |
| **Fraud-Prone** | Ghost bids, collusive patterns, and inflated declarations go undetected |

---

## 🚀 The Vision

**Anveshane AI** solves all five at once:

1. **Automated Document Intelligence** — No more manual scanning of 100-page PDFs. Gemini 2.5 Flash reads, extracts, and structures every document in seconds.
2. **Evidence-Based Ranking** — Every decision is backed by a source signal: page number, specific clause, extracted value, and confidence score.
3. **Public Transparency** — A no-login citizen portal shows who won, why, and what happened during delivery.
4. **Full Auditability** — Every action — evaluation, override, login — is logged immutably with timestamps, user IDs, and model versions.
5. **Smart Scoring** — Contractors are ranked not just on compliance, but on their current workload and delivery history.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Anveshane AI Platform                    │
├──────────────┬──────────────────────┬───────────────────────┤
│   Admin UI   │   Contractor Portal  │   Citizen Dashboard   │
├──────────────┴──────────────────────┴───────────────────────┤
│                     FastAPI Backend (Python)                  │
├──────────────────────────────────────────────────────────────┤
│  Document     │  Criteria    │  Evaluation  │ Explainability │
│  Processor    │  Extractor   │  Engine      │ Engine         │
│  (OCR+NLP)    │  (Gemini)    │  (Hybrid)    │ (Evidence link)│
├──────────────────────────────────────────────────────────────┤
│  Bidder       │  Audit       │  Citizen     │ Auth           │
│  Parser       │  Logger      │  Service     │ (JWT + bcrypt) │
├──────────────────────────────────────────────────────────────┤
│           SQLite + SQLAlchemy (WAL mode, audit-ready)        │
├──────────────────────────────────────────────────────────────┤
│                 Gemini 2.5 Flash / 1.5 Pro                   │
└──────────────────────────────────────────────────────────────┘
```

**Request flow:**
```
Upload Tender/Submission
    → Document Processor (PDF/DOCX/Image → text + confidence)
    → Criteria Extractor (Gemini extracts eligibility rules)
    → Bidder Parser (semantic normalization of submission)
    → Evaluation Engine (KO / Scored / Remediable matching)
    → Explainability Engine (evidence-linked verdicts)
    → Audit Logger (immutable JSONL + SQLite)
    → Citizen Service (sanitized public view)
```

---

## ✨ Core Features — The 19 Pillars

### 👥 Shared Features (All Roles)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Profile & Theme Engine** | Dark/Light mode with Ghibli-inspired "Fluid Glass" aesthetic |
| 2 | **Explainability Timeline** | Full traceability from tender creation to final award |
| 3 | **Inbox & Workspace** | Real-time system notifications and task management |
| 4 | **Help & Support Center** | Role-based support documentation and FAQs |
| 5 | **Technical Troubleshoot** | One-click cache clearing and system health check |

### 👑 Admin Capabilities

| # | Feature | Description |
|---|---------|-------------|
| 6 | **Tender Lifecycle Management** | Create tenders, set deadlines, publish documents, manage status |
| 7 | **Submission Tracking** | Real-time monitoring of all incoming bidder proposals |
| 8 | **Evaluations Review** | AI-powered compliance checking with S_T + S_OB + S_P scoring |
| 9 | **Contractor Performance Audit** | Merit/Demerit point tracking based on delivery history |
| 10 | **System Activity Logs** | Full audit trail for every action — evaluation, override, login |
| 11 | **Control Panel** | Administrative settings, user management, system health |

### 🏗️ Contractor Tools

| # | Feature | Description |
|---|---------|-------------|
| 12 | **Opportunity Discovery** | Intelligent search for relevant open tenders by sector and deadline |
| 13 | **AI PDF Analyzer** | Upload a tender → Gemini instantly checks your eligibility |
| 14 | **Smart Bid Submission** | Streamlined document upload and submission workflow |
| 15 | **Orderbook & Contracts** | Comprehensive view of active projects and contract history |
| 16 | **Activity Dashboard** | Bid success rates, win/loss breakdown, and status overview |

### 🇮🇳 Citizen Access Points

| # | Feature | Description |
|---|---------|-------------|
| 17 | **Awarded Tenders Portal** | Public record of all finalized procurement decisions — no login required |
| 18 | **Sector Distribution Analytics** | Visual breakdown of spending across Infrastructure, IT, Agriculture, Education |
| 19 | **Financial Amount Analytics** | High-level insights into public spending values and project investment |

> **Bonus (V2 roadmap):** Anonymous "Report Suspicious Activity" tab — any citizen can flag mischievous activity with evidence upload.

---

## 🤖 AI Evaluation Pipeline

Anveshane AI runs a 6-module evaluation pipeline, each implemented as a distinct Python class in `src/`:

### 1. `DocumentProcessor` — `src/document_processor.py`

Handles all input formats:

```
PDF  → PyPDF2 text extraction (confidence: 0.9 if text found, 0.3 if empty)
DOCX → python-docx / zipfile + XML parsing
Image / Scan → pytesseract OCR (confidence: 0.7 if text found, 0.2 if empty)
```

Returns `(text: str, confidence: float, page_count: int)` for every document.

### 2. `CriteriaExtractor` — `src/criteria_extractor.py`

Parses the tender document and extracts structured eligibility criteria:

- Annual Turnover (currency, threshold matching)
- ISO Certifications (text, boolean check)
- GST / PAN Registration (text, format validation)
- Years of Experience (integer, range check)
- Any custom criteria found in the document via Gemini semantic extraction

Each criterion is classified as:

| Type | Meaning |
|------|---------|
| `required: True` | **Knock-Out (KO)** — failure = rejection candidate |
| `required: False` | **Scored** — contributes to ranking |
| Remediable | Triggers clarification workflow instead of rejection |

### 3. `BidderParser` — `src/bidder_parser.py`

Extracts and normalizes values from bidder submissions:

- Semantic normalization: `"Gross Receipts"` → `Turnover`, `"Company Registration"` → `GST`
- Field-level confidence scores for every extracted value
- Handles format variations across different bidder document styles

### 4. `EvaluationEngine` — `src/evaluation_engine.py`

Core matching logic:

```python
confidence_threshold = 0.7      # Above → use AI result directly
manual_review_threshold = 0.6   # Below → flag for human review
```

Decision matrix:

| Condition | Decision |
|-----------|----------|
| All KO criteria met, confidence ≥ 0.7 | `ELIGIBLE` |
| Any KO criterion failed | `NOT_ELIGIBLE` |
| Confidence < 0.6 on any criterion | `MANUAL_REVIEW` |
| Data missing or ambiguous | `MANUAL_REVIEW` (never silent rejection) |

### 5. `ExplainabilityEngine` — `src/explainability.py`

Generates a complete explanation for every verdict:

```json
{
  "bidder_name": "ABC Constructions Pvt. Ltd.",
  "final_decision": "MANUAL_REVIEW",
  "confidence": "71%",
  "criteria_breakdown": [
    {
      "criterion": "Annual Turnover ≥ ₹5 Cr",
      "extracted_value": "₹4.2 Cr (Balance Sheet) vs ₹6.8 Cr (Self-Declaration)",
      "confidence": "62%",
      "status": "CLARIFICATION_REQUIRED",
      "reason": "Contradiction detected across documents"
    }
  ],
  "key_findings": ["Contradiction in turnover figures across documents"],
  "recommendations": ["Request certified CA-audited balance sheet for FY2023"]
}
```

### 6. `AuditLogger` — `src/audit_logger.py`

Writes append-only `audit_logs/<tender_id>_audit.jsonl` entries for every:
- Evaluation event
- Manual override (with mandatory reason)
- Decision status change

Each entry includes: `timestamp`, `action`, `user_id`, `bidder_name`, `tender_id`, `decision`, `reason`, `override: bool`, `audit_id`.

---

## 📐 Smart Scoring Formula

Anveshane AI ranks eligible contractors using a composite score — not just a binary pass/fail:

```
Total Score  =  S_T  +  S_OB  +  S_P
```

| Component | Name | What it measures |
|-----------|------|-----------------|
| **S_T** | Tender Score | Compliance with all tender criteria (financial, technical, compliance) |
| **S_OB** | Order Book Score | Current contractor workload — de-prioritizes overloaded contractors |
| **S_P** | Performance Score | Historical merit/demerit points from past project deliveries |

**S_OB logic:** A contractor with a full order book is down-ranked. This prevents awarding contracts to companies that cannot execute — catching delivery risk *before* it becomes a project delay.

**S_P tracking** (per `User` model):
- `merit_points`: earned for on-time delivery, quality outcomes
- `demerit_points`: incurred for delays, penalties, subcontractor substitution
- `on_time_completions` / `total_projects`: raw delivery statistics

---

## 🗄️ Data Models

### Core Pydantic Models (`src/models.py`)

```python
DecisionStatus: ELIGIBLE | NOT_ELIGIBLE | MANUAL_REVIEW

Evidence            # source_document, page_number, extracted_text, confidence, reasoning
CriterionEvaluation # criterion_id, status, evidence[], confidence, reason
BidderEvaluationResult # bidder_name, final_decision, criterion_evaluations[], audit_id
EligibilityCriterion   # criterion_id, name, required (KO flag), data_type, expected_value
TenderDocument         # tender_id, title, criteria[], extraction_confidence
BidderSubmission       # bidder_name, extracted_fields{}, extraction_confidence
AuditLog               # timestamp, action, decision, reason, override, audit_id
```

### Database Tables (`src/database.py`)

SQLite with WAL mode enabled for concurrent reads:

```
users              → id, email, role, merit_points, demerit_points, on_time_completions
tenders            → id, title, sector, status, awarded_to, delay_days, penalty_applied
bidder_submissions → id, tender_id, bidder_id, document_path, status
evaluations        → id, tender_id, decision, confidence, criteria_breakdown (JSON), audit_id
overrides          → id, evaluation_id, original_decision, new_decision, reason, overridden_by
```

**Performance indexes:**
```python
Index("ix_eval_tender_decision",   Evaluation.tender_id, Evaluation.decision)
Index("ix_eval_tender_confidence", Evaluation.tender_id, Evaluation.confidence)
Index("ix_sub_tender_status",      BidderSubmission.tender_id, BidderSubmission.status)
```

**Roles:** `admin` | `contractor` | `evaluator` | `citizen`

---

## 🌐 API Reference

All endpoints served at `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register new user (contractor or admin) |
| `POST` | `/auth/login` | Login → returns JWT token |
| `GET`  | `/auth/me` | Get current user profile |
| `PUT`  | `/auth/me` | Update user profile |

### Tenders (Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST`   | `/tenders/` | Create new tender with document upload |
| `GET`    | `/tenders/` | List all tenders |
| `GET`    | `/tenders/{id}` | Get tender detail |
| `PUT`    | `/tenders/{id}/status` | Update tender status (publish, award, close) |

### Submissions (Contractor)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tenders/{id}/submit` | Upload bid submission documents |
| `GET`  | `/submissions/my` | List contractor's own submissions |
| `POST` | `/contractor/analyze-pdf` | AI PDF analyzer — instant eligibility check |

### Evaluations (Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tenders/{id}/evaluate` | Trigger AI evaluation for all submissions |
| `GET`  | `/tenders/{id}/evaluations` | List evaluation results |
| `POST` | `/evaluations/{id}/override` | Override AI verdict (reason mandatory) |

### Citizen (Public — No Auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/citizen/tenders` | List all publicly awarded tenders |
| `GET` | `/citizen/tenders/{id}` | Tender detail: winner, top 3, contract value, timeline |
| `GET` | `/citizen/tenders/{id}/explanation` | Plain-language explanation of award decision |
| `GET` | `/citizen/sectors` | Sector distribution analytics |
| `GET` | `/citizen/financials` | Financial amount analytics |

### Dashboard & Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/dashboard/stats` | Admin dashboard KPIs |
| `GET` | `/dashboard/analytics` | Sector-wise tender and spend breakdown |
| `GET` | `/admin/audit-logs` | Full system audit trail |

---

## 🛠️ Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **AI / LLM** | Google Gemini 2.5 Flash | latest | Document extraction, criteria parsing, eligibility reasoning |
| **AI / LLM (fallback)** | Gemini 1.5 Pro | latest | Complex multi-document analysis |
| **Backend** | FastAPI | 0.104.1 | High-performance async API server |
| **ASGI Server** | Uvicorn | 0.24.0 | Production-grade ASGI runner |
| **Database ORM** | SQLAlchemy | 2.0.23 | Audit-ready structured storage |
| **Database** | SQLite (WAL mode) | — | Portable, concurrent, audit-friendly |
| **Auth** | python-jose + passlib | 3.3.0 / 1.7.4 | JWT tokens + bcrypt password hashing |
| **PDF Parsing** | PyPDF2 | 3.0.1 | Typed PDF text extraction |
| **OCR** | pytesseract + Pillow | 0.3.10 / 10.1.0 | Scanned document and image processing |
| **Validation** | Pydantic | 2.5.0 | Request/response schema validation |
| **Frontend** | Vanilla JS / HTML5 / CSS3 | ES6+ | No-framework, Glassmorphism "Fluid Glass" UI |
| **Design Aesthetic** | Custom CSS | — | Dark/light mode, Ghibli-inspired backgrounds |
| **AI SDK** | google-generativeai | 0.3.1 | Gemini API client |
| **File Upload** | python-multipart | 0.0.6 | Multipart form handling |

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.9+
- Tesseract OCR installed on your system ([installation guide](https://github.com/tesseract-ocr/tesseract))
- Google AI Studio API key ([get one here](https://aistudio.google.com/))

### 1. Clone & Environment Setup

```bash
git clone <your-repo-url>
cd anveshane-ai
```

Create `.env` from the provided template:

```bash
cp .env.examp .env
```

Edit `.env`:

```env
GEMINI_API_KEY=your_primary_gemini_key_here
GEMINI_API_KEY2=your_secondary_gemini_key_here   # optional, used as fallback
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Full dependency list:

```
fastapi==0.104.1          # API framework
uvicorn==0.24.0           # ASGI server
pydantic==2.5.0           # Validation
pydantic-settings==2.1.0  # Settings management
python-dotenv==1.0.0      # Env vars
PyPDF2==3.0.1             # PDF parsing
pytesseract==0.3.10       # OCR
pillow==10.1.0            # Image processing
sqlalchemy==2.0.23        # ORM
python-multipart==0.0.6   # File uploads
python-jose==3.3.0        # JWT
passlib==1.7.4            # Password hashing
bcrypt==4.1.1             # Bcrypt backend
google-generativeai==0.3.1 # Gemini AI
requests==2.31.0          # HTTP client
```

### 3. Initialize Database

The database initializes automatically on first run. To seed test users manually:

```bash
python seed_users.py
```

To run database migrations:

```bash
python migrate_db.py
```

### 4. Start the Server

```bash
python backend_api.py
```

Or with uvicorn directly:

```bash
uvicorn backend_api:app --reload --host 0.0.0.0 --port 8000
```

Application available at: **`http://localhost:8000`**

Interactive API docs: **`http://localhost:8000/docs`**

---

## 📖 Usage Guide

### Admin Flow

1. Login with admin credentials from the table below
2. Navigate to **Tender Management** → Create a new tender, set sector and deadline, upload the tender document
3. Monitor incoming submissions in **Submission Tracking**
4. Click **Run AI Evaluation** — Gemini evaluates all submissions against extracted criteria
5. Review AI verdicts in **Evaluations Review** — each decision shows criterion breakdown, confidence, and source reference
6. Override any verdict if needed (a written reason is mandatory and permanently logged)
7. **Publish** the result — the winner becomes visible on the Citizen Portal

### Contractor Flow

1. Register or login as a contractor using the credentials below
2. Browse **Open Tenders** in Opportunity Discovery — filter by sector
3. Use **AI PDF Analyzer** — upload the tender document and get an instant eligibility pre-check before investing time in a full bid
4. Submit via **Smart Bid Submission** — upload all required documents in one workflow
5. Track your bid status and history in **Orderbook & Contracts**

### Citizen Flow

No login required. Visit `http://localhost:8000` → click **About** → **Awarded Tenders**.

You can:
- View the winning bidder, top 3 candidates, and plain-language reason for selection
- Browse sector-wise distribution of public spending
- See financial analytics across Infrastructure, IT, Agriculture, Education, and Insurance projects

---

## 🔑 Test Credentials

> ⚠️ **These credentials are for local development and demo purposes only.** Do not use in production.

After running `python seed_users.py`, the following accounts are available:

| Role | Email | Password | Access |
|------|-------|----------|--------|
| **Admin** | `admin@tender.com` | `Admin@123` | Full platform — create tenders, run evaluations, override verdicts, view audit logs |
| **Contractor** | `contractor@tender.com` | `Contractor@123` | Discover tenders, AI PDF analyzer, submit bids, view orderbook |
| **Contractor** | `contractor2@tender.com` | `Contractor@123` | Same as above — second contractor account for multi-bidder testing |
| **Citizen** | `citizen@tender.com` | `Citizen@123` | Public portal — awarded tenders, sector analytics, financial insights |
| **Citizen** | `test_user1@example.com` | `User@123` | Same as above — alternate citizen test account |

### Quick Login Flow

```bash
# Start the server
python backend_api.py

# Open in browser
http://localhost:8000

# Login with any credentials above based on the role you want to explore
```

### Role Capabilities at a Glance

```
Admin       →  Everything. Tender lifecycle, AI evaluation, overrides, audit trail.
Contractor  →  Tender discovery, AI eligibility check, bid submission, contract history.
Citizen     →  No login needed for public portal. Login unlocks saved preferences.
```

---

## 📜 Audit & Compliance

Anveshane AI is designed for legal defensibility from the ground up.

### Audit Log Structure

Every evaluation writes a JSONL entry to `audit_logs/<tender_id>_audit.jsonl`:

```json
{
  "timestamp": "2024-01-15T14:32:10.123Z",
  "action": "EVALUATION",
  "user_id": "admin_001",
  "bidder_name": "ABC Constructions Pvt. Ltd.",
  "tender_id": "TENDER_2024_001",
  "decision": "MANUAL_REVIEW",
  "reason": "Turnover figure contradicts across Balance Sheet and Self-Declaration",
  "override": false,
  "audit_id": "3f7a2b1c-..."
}
```

### Override Logging

Any human override of an AI verdict is permanently recorded in the `overrides` table:

```
original_decision  →  new_decision
reason             (mandatory — cannot be empty)
overridden_by      (user ID)
overridden_at      (timestamp)
```

### Non-Negotiables

- **No silent rejections** — every `NOT_ELIGIBLE` and `MANUAL_REVIEW` verdict includes an explicit, source-linked reason
- **Immutable logs** — audit JSONL files are append-only
- **Override accountability** — every manual change is permanently attributed to the officer who made it
- **Confidence transparency** — every extracted value carries a confidence score; values below threshold trigger review, never auto-rejection

---

## 🇮🇳 Citizen Transparency Portal

The public portal (`/citizen/*` endpoints) exposes a sanitized view of procurement outcomes. Implemented in `src/citizen_service.py`, it:

- **Never exposes** raw evaluation payloads, internal document paths, or audit-only data
- Selects the public winner using: explicit `awarded_to` field → highest-confidence eligible bidder → highest-confidence bidder overall
- Builds plain-language award reasons from criteria breakdown data
- Shows top 3 bidders with their key strengths in a comparison table
- Tracks `delay_days` and `penalty_applied` for post-award accountability

**Public statuses** mapped for citizen display:
```
published / completed / finalized → "completed"
awarded                           → "ongoing"
```

---

## 📊 Sector Intelligence

Anveshane AI tracks public spending across 5 sectors:

| Sector | Current Share | Tender Count | Focus Areas |
|--------|--------------|--------------|-------------|
| **Infrastructure** | 40% | 120 | Roads, construction, water supply |
| **Tech / IT** | 30% | 75 | Digital systems, manpower, hardware, service delivery |
| **Education** | 10% | 26 | School devices, books, uniforms, nutrition support |
| **Agriculture** | 10% | 30 | Watershed monitoring, farm mechanization |
| **Insurance** | 10% | 20 | Mediclaim policies |

The **Sector Distribution Dashboard** available to citizens shows real-time percentage breakdown with trend analysis.

---

## 🚀 Roadmap

| Version | Status | Focus |
|---------|--------|-------|
| **V1** | ✅ Shipped | Core evaluation pipeline, 3-role auth, citizen portal, audit trail, human override |
| **V2** | 🔄 In Progress | Live Contradiction Engine, Bidder Behavioral Genome, collusion detection, bounding-box explainability, anonymous citizen report tab |
| **V3** | 🗓️ Planned | Blockchain immutable award records, predictive delay warning engine, multi-modal scanned handwriting, GeM API integration, national deployment |

### V2 Highlights (Coming Soon)

**Live Contradiction Engine** — Detects conflicting values across a single bidder's own documents (e.g., turnover ₹4.2 Cr in the Balance Sheet vs ₹6.8 Cr in the Self-Declaration) and auto-drafts a targeted clarification query.

**Bidder Behavioral Genome** — Builds a longitudinal risk profile across every tender a company has ever participated in — bid-win ratios, post-award behavior, ghost bid patterns, cross-tender team overlap. Advisory only; never an automated disqualifier.

**Field-Level Confidence Heatmaps** — Visual overlay on source documents showing which fields were extracted with what confidence.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes with tests
4. Commit: `git commit -m "feat: add your feature"`
5. Push and open a Pull Request

Please ensure all new evaluation logic maintains the **no silent rejection** principle — any ambiguous case must be routed to `MANUAL_REVIEW` with a human-readable reason.

---

## 🔐 Security Notes

- Change `SECRET_KEY` in `src/auth.py` before any production deployment
- Store `.env` securely — never commit API keys to version control
- `credentials.txt` is for local development only — use a secrets manager in production
- All password storage uses bcrypt hashing via passlib

---

## 📄 License

This project was built for the CRPF AI for Bharat Hackathon 2025.

---

<div align="center">

**Anveshane AI** — *Making procurement faster, fairer, and finally transparent.*

`FastAPI` · `Gemini 2.5 Flash` · `SQLite` · `Vanilla JS` · `19 Features` · `3 Roles` · `100% Auditable`

</div>
