"""
Core evaluation engine for tender eligibility assessment
"""
from typing import List
from datetime import datetime
import uuid
from src.models import (
    BidderEvaluationResult,
    CriterionEvaluation,
    DecisionStatus,
    Evidence,
    TenderDocument,
    BidderSubmission,
    EligibilityCriterion
)


class EvaluationEngine:
    """Core engine for evaluating bidder eligibility"""
    
    def __init__(self):
        """Initialize evaluation engine"""
        self.confidence_threshold = 0.7
        self.manual_review_threshold = 0.6
    
    def evaluate_bidder(
        self,
        tender_doc: TenderDocument,
        bidder_submission: BidderSubmission
    ) -> BidderEvaluationResult:
        """
        Evaluate bidder against tender criteria
        """
        criterion_evaluations = []
        
        for criterion in tender_doc.criteria:
            evaluation = self._evaluate_criterion(
                criterion,
                bidder_submission,
                tender_doc.tender_id
            )
            criterion_evaluations.append(evaluation)
        
        # Determine final decision
        final_decision = self._determine_final_decision(criterion_evaluations)
        overall_confidence = self._calculate_overall_confidence(criterion_evaluations)
        
        audit_id = str(uuid.uuid4())
        
        return BidderEvaluationResult(
            bidder_name=bidder_submission.bidder_name,
            tender_id=tender_doc.tender_id,
            final_decision=final_decision,
            overall_confidence=overall_confidence,
            criterion_evaluations=criterion_evaluations,
            summary=self._generate_summary(criterion_evaluations, final_decision),
            timestamp=datetime.now(),
            audit_id=audit_id
        )
    
    def _evaluate_criterion(
        self,
        criterion: EligibilityCriterion,
        bidder_submission: BidderSubmission,
        tender_id: str
    ) -> CriterionEvaluation:
        """Evaluate a single criterion"""
        
        # Check if field exists in bidder submission
        field_key = self._map_criterion_to_field(criterion.name)
        
        if field_key not in bidder_submission.extracted_fields:
            # Missing data - flag for manual review
            evidence = Evidence(
                criterion_id=criterion.criterion_id,
                criterion_name=criterion.name,
                source_document=bidder_submission.source_document,
                page_number=1,
                extracted_text="NOT FOUND",
                confidence=0.0,
                reasoning="Required field not found in bidder submission"
            )
            
            status = DecisionStatus.MANUAL_REVIEW if criterion.required else DecisionStatus.ELIGIBLE
            
            return CriterionEvaluation(
                criterion_id=criterion.criterion_id,
                criterion_name=criterion.name,
                status=status,
                evidence=[evidence],
                confidence=0.0,
                reason=f"Missing: {criterion.name}"
            )
        
        # Field found - evaluate it
        field_value = bidder_submission.extracted_fields[field_key]
        confidence = self._calculate_field_confidence(field_value)
        
        # Determine if criterion is met
        is_met = self._check_criterion_met(criterion, field_value)
        
        evidence = Evidence(
            criterion_id=criterion.criterion_id,
            criterion_name=criterion.name,
            source_document=bidder_submission.source_document,
            page_number=1,
            extracted_text=str(field_value),
            confidence=confidence,
            reasoning=f"Field '{criterion.name}' found and evaluated"
        )
        
        if confidence < self.manual_review_threshold:
            status = DecisionStatus.MANUAL_REVIEW
            reason = f"Low confidence ({confidence:.0%}) in extracted value"
        elif is_met:
            status = DecisionStatus.ELIGIBLE
            reason = f"Criterion met: {criterion.name}"
        else:
            status = DecisionStatus.NOT_ELIGIBLE if criterion.required else DecisionStatus.ELIGIBLE
            reason = f"Criterion not met: {criterion.name}"
        
        return CriterionEvaluation(
            criterion_id=criterion.criterion_id,
            criterion_name=criterion.name,
            status=status,
            evidence=[evidence],
            confidence=confidence,
            reason=reason
        )
    
    def _map_criterion_to_field(self, criterion_name: str) -> str:
        """Map criterion name to bidder submission field"""
        mapping = {
            "Annual Turnover": "turnover",
            "GST Registration": "gst_number",
            "Years of Experience": "experience_years",
            "ISO Certification": "iso_certifications",
            "PAN Registration": "pan_number"
        }
        return mapping.get(criterion_name, criterion_name.lower())
    
    def _calculate_field_confidence(self, field_value) -> float:
        """Calculate confidence in extracted field"""
        if field_value is None:
            return 0.0
        
        if isinstance(field_value, dict):
            return field_value.get("confidence", 0.8)
        
        return 0.85
    
    def _check_criterion_met(self, criterion: EligibilityCriterion, value) -> bool:
        """Check if criterion is met by the value"""
        # Simple validation - in production, this would be more sophisticated
        if value is None:
            return False
        
        if isinstance(value, dict):
            return value.get("value") is not None
        
        return bool(value)
    
    def _determine_final_decision(
        self,
        criterion_evaluations: List[CriterionEvaluation]
    ) -> DecisionStatus:
        """Determine final decision based on criterion evaluations"""
        
        # Check for manual review flags
        for eval in criterion_evaluations:
            if eval.status == DecisionStatus.MANUAL_REVIEW:
                return DecisionStatus.MANUAL_REVIEW
        
        # Check for not eligible
        for eval in criterion_evaluations:
            if eval.status == DecisionStatus.NOT_ELIGIBLE:
                return DecisionStatus.NOT_ELIGIBLE
        
        # All criteria met
        return DecisionStatus.ELIGIBLE
    
    def _calculate_overall_confidence(
        self,
        criterion_evaluations: List[CriterionEvaluation]
    ) -> float:
        """Calculate overall confidence score"""
        if not criterion_evaluations:
            return 0.0
        
        total_confidence = sum(eval.confidence for eval in criterion_evaluations)
        return total_confidence / len(criterion_evaluations)
    
    def _generate_summary(
        self,
        criterion_evaluations: List[CriterionEvaluation],
        final_decision: DecisionStatus
    ) -> str:
        """Generate human-readable summary"""
        eligible_count = sum(1 for e in criterion_evaluations if e.status == DecisionStatus.ELIGIBLE)
        not_eligible_count = sum(1 for e in criterion_evaluations if e.status == DecisionStatus.NOT_ELIGIBLE)
        review_count = sum(1 for e in criterion_evaluations if e.status == DecisionStatus.MANUAL_REVIEW)
        
        summary = f"Decision: {final_decision.value}\n"
        summary += f"Criteria Met: {eligible_count}/{len(criterion_evaluations)}\n"
        
        if not_eligible_count > 0:
            summary += f"Failed Criteria: {not_eligible_count}\n"
        
        if review_count > 0:
            summary += f"Requires Manual Review: {review_count}\n"
        
        return summary
