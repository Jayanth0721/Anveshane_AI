# GEMINI.md - Project Guidelines

## 🎯 Project Vision
AI-powered procurement evaluation system focused on transparency, automation, and auditability.

## 🧠 Core Principles
- **Explainability First:** Every decision must be backed by evidence (source document, page reference, reasoning).
- **No Silent Rejections:** Never disqualify a bidder without a clear reason or flagging for manual review.
- **Auditability:** Maintain a full traceability log from input to extraction to decision.
- **Confidence Awareness:** High uncertainty (low OCR confidence or missing data) must trigger manual review.

## 🛠 Technical Standards
- **Backend:** FastAPI (Python).
- **Database:** SQLite (SQLAlchemy models in `src/models.py`).
- **OCR/NLP:** Document processing pipeline using LLMs and layout-aware parsing.
- **Structure:**
    - `src/`: Core application logic.
    - `backend_api.py`: API entry point.
    - `audit_logs/`: Directory for traceability logs.
    - `uploads/`: Storage for tenders and submissions.

## 🚀 Development Workflow
1. **Research:** Map the codebase and validate assumptions.
2. **Strategy:** Plan changes with a focus on maintainability and type safety.
3. **Execution:** Surgical updates with mandatory validation.
4. **Validation:** Ensure logic changes are verified with tests and do not break the audit trail.

## 🧪 Testing & Validation
- Always update or add tests in the relevant test suite (if available).
- For the evaluation engine, verify that decisions include the required explainability metadata.

## 🧾 Audit Trail
Any change to the evaluation logic must ensure that `audit_logger.py` continues to capture all necessary state transitions.
