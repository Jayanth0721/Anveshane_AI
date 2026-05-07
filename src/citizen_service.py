"""
Citizen transparency service.

Builds a sanitized public_view of tender outcomes so the citizen APIs never
return raw evaluation payloads, internal document paths, or audit-only data.
"""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.database import Evaluation, Tender
from src.schemas import (
    CitizenComparisonRow,
    CitizenTenderDetail,
    CitizenTenderExplanation,
    CitizenTenderListItem,
)


PUBLIC_STATUSES = {
    "published": "completed",
    "completed": "completed",
    "finalized": "completed",
    "awarded": "ongoing",
}

PUBLISHED_STATUSES = {"published", "completed", "finalized", "awarded"}


def _normalize_public_status(status: Optional[str]) -> str:
    return PUBLIC_STATUSES.get((status or "").lower(), "ongoing")


def _get_tender_department(tender: Tender) -> str:
    return tender.department or "Procurement Department"


def _get_ranked_evaluations(db: Session, tender_id: str) -> List[Evaluation]:
    return (
        db.query(Evaluation)
        .filter(Evaluation.tender_id == tender_id)
        .order_by(Evaluation.confidence.desc(), Evaluation.evaluated_at.asc())
        .all()
    )


def _select_public_winner(tender: Tender, evaluations: List[Evaluation]) -> Optional[Evaluation]:
    if not evaluations:
        return None

    if tender.awarded_to:
        explicit = next((ev for ev in evaluations if ev.bidder_name == tender.awarded_to), None)
        if explicit:
            return explicit

    eligible = [ev for ev in evaluations if ev.decision == "ELIGIBLE"]
    if eligible:
        return eligible[0]

    return evaluations[0]


def _extract_key_strength(evaluation: Evaluation) -> str:
    if evaluation.decision == "ELIGIBLE":
        default_strength = "Met the required evaluation criteria"
    elif evaluation.decision == "MANUAL_REVIEW":
        default_strength = "Requires additional verification before closure"
    else:
        default_strength = "Did not satisfy all mandatory requirements"

    if not evaluation.criteria_breakdown:
        return default_strength

    try:
        breakdown = json.loads(evaluation.criteria_breakdown)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default_strength

    proposal_bits = []
    for item in breakdown:
        if item.get("criterion_name") in {"Proposal Amount", "Completion Timeline"}:
            reason = item.get("reason")
            if reason and reason != "Not found":
                proposal_bits.append(reason)

    if proposal_bits:
        return "; ".join(proposal_bits[:2])

    for item in breakdown:
        if str(item.get("status", "")).upper() in {"PASS", "ELIGIBLE", "MET"}:
            criterion = item.get("criterion_name") or "key requirements"
            return f"Strong performance on {criterion}"

    return default_strength


def _build_public_reasons(winner: Optional[Evaluation], evaluations: List[Evaluation]) -> List[str]:
    if not winner:
        return ["Evaluation is still being finalized."]

    reasons: List[str] = []

    if winner.decision == "ELIGIBLE":
        reasons.append("Met all mandatory criteria")
    elif winner.decision == "MANUAL_REVIEW":
        reasons.append("Cleared the initial screening with items flagged for review")
    else:
        reasons.append("Achieved the strongest overall result in the final comparison")

    reasons.append(_extract_key_strength(winner))

    if winner.summary and "Smart tender score" in winner.summary:
        reasons.append("Ranked using eligibility, proposal amount, and delivery speed")

    if len(evaluations) > 1:
        reasons.append("Delivered one of the strongest overall bids among evaluated bidders")
    else:
        reasons.append("Satisfied the public award conditions for this tender")

    unique_reasons: List[str] = []
    for reason in reasons:
        if reason and reason not in unique_reasons:
            unique_reasons.append(reason)
    return unique_reasons[:3]


def _ensure_public_tender(tender: Optional[Tender], winner: Optional[Evaluation]) -> None:
    if not tender:
        raise ValueError("Tender not found")

    # Citizen view is limited to admin-published results only.
    if (tender.status or "").lower() not in PUBLISHED_STATUSES or not winner:
        raise PermissionError("Tender is not yet available for public viewing")


def list_public_tenders(db: Session) -> List[CitizenTenderListItem]:
    items: List[CitizenTenderListItem] = []

    tenders = db.query(Tender).order_by(Tender.created_at.desc()).all()
    for tender in tenders:
        if (tender.status or "").lower() not in PUBLISHED_STATUSES:
            continue
        evaluations = _get_ranked_evaluations(db, tender.id)
        winner = _select_public_winner(tender, evaluations)
        if not winner:
            continue

        items.append(
            CitizenTenderListItem(
                tender_id=tender.id,
                title=tender.title,
                department=_get_tender_department(tender),
                status=_normalize_public_status(tender.status),
                sector=tender.sector or "General",
                deadline=tender.application_deadline,
            )

        )

    return items


def get_public_tender_detail(db: Session, tender_id: str) -> CitizenTenderDetail:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    evaluations = _get_ranked_evaluations(db, tender_id)
    winner = _select_public_winner(tender, evaluations)
    _ensure_public_tender(tender, winner)

    top_bidders = [ev.bidder_name for ev in evaluations[:3]]
    comparison_rows = [
        CitizenComparisonRow(
            bidder=ev.bidder_name,
            status=ev.decision.replace("_", " ").title(),
            key_strength=_extract_key_strength(ev),
        )
        for ev in evaluations[:3]
    ]

    return CitizenTenderDetail(
        tender_id=tender.id,
        title=tender.title,
        winning_bidder=winner.bidder_name,
        top_bidders=top_bidders,
        contract_value=tender.investment_amount or "Not disclosed",
        duration=f"{tender.duration_days} days" if tender.duration_days else "Not disclosed",
        status=_normalize_public_status(tender.status),
        delay_days=tender.delay_days or 0,
        penalty_applied=bool(tender.penalty_applied),
        last_updated=tender.last_updated or tender.updated_at or datetime.utcnow(),
        comparative_table=comparison_rows,
        verified_decision=winner.decision in {"ELIGIBLE", "MANUAL_REVIEW"},
    )


def get_public_tender_explanation(db: Session, tender_id: str) -> CitizenTenderExplanation:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    evaluations = _get_ranked_evaluations(db, tender_id)
    winner = _select_public_winner(tender, evaluations)
    _ensure_public_tender(tender, winner)

    return CitizenTenderExplanation(
        winner=winner.bidder_name,
        reasons=_build_public_reasons(winner, evaluations),
        confidence=round(float(winner.confidence or 0), 2),
    )
