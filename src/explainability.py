"""
Explainability layer - evidence linking and decision explanation
"""
from typing import List, Dict
from src.models import BidderEvaluationResult, CriterionEvaluation


class ExplainabilityEngine:
    """Generate explainable, evidence-backed decision explanations"""
    
    def generate_explanation(
        self,
        evaluation_result: BidderEvaluationResult
    ) -> Dict[str, any]:
        """
        Generate comprehensive explanation for evaluation decision
        """
        explanation = {
            "bidder_name": evaluation_result.bidder_name,
            "tender_id": evaluation_result.tender_id,
            "final_decision": evaluation_result.final_decision.value,
            "confidence": f"{evaluation_result.overall_confidence:.0%}",
            "timestamp": evaluation_result.timestamp.isoformat(),
            "audit_id": evaluation_result.audit_id,
            "criteria_breakdown": [],
            "key_findings": [],
            "recommendations": []
        }
        
        # Add criterion-level explanations
        for criterion_eval in evaluation_result.criterion_evaluations:
            criterion_explanation = self._explain_criterion(criterion_eval)
            explanation["criteria_breakdown"].append(criterion_explanation)
        
        # Generate key findings
        explanation["key_findings"] = self._extract_key_findings(
            evaluation_result.criterion_evaluations
        )
        
        # Generate recommendations
        explanation["recommendations"] = self._generate_recommendations(
            evaluation_result
        )
        
        return explanation
    
    def _explain_criterion(self, criterion_eval: CriterionEvaluation) -> Dict:
        """Generate explanation for single criterion evaluation"""
        
        status_symbol = {
            "ELIGIBLE": "✔",
            "NOT_ELIGIBLE": "❌",
            "MANUAL_REVIEW": "⚠"
        }
        
        explanation = {
            "criterion_id": criterion_eval.criterion_id,
            "criterion_name": criterion_eval.criterion_name,
            "status": criterion_eval.status.value,
            "status_symbol": status_symbol.get(criterion_eval.status.value, "?"),
            "confidence": f"{criterion_eval.confidence:.0%}",
            "reason": criterion_eval.reason,
            "evidence": []
        }
        
        # Add evidence details
        for evidence in criterion_eval.evidence:
            evidence_detail = {
                "source_document": evidence.source_document,
                "page_number": evidence.page_number,
                "extracted_value": evidence.extracted_text,
                "confidence": f"{evidence.confidence:.0%}",
                "reasoning": evidence.reasoning
            }
            explanation["evidence"].append(evidence_detail)
        
        return explanation
    
    def _extract_key_findings(
        self,
        criterion_evaluations: List[CriterionEvaluation]
    ) -> List[str]:
        """Extract key findings from evaluation"""
        findings = []
        
        # Find passed criteria
        passed = [e for e in criterion_evaluations if e.status.value == "ELIGIBLE"]
        if passed:
            findings.append(f"✔ {len(passed)} criteria met")
        
        # Find failed criteria
        failed = [e for e in criterion_evaluations if e.status.value == "NOT_ELIGIBLE"]
        if failed:
            failed_names = ", ".join([e.criterion_name for e in failed])
            findings.append(f"❌ Failed: {failed_names}")
        
        # Find criteria needing review
        review = [e for e in criterion_evaluations if e.status.value == "MANUAL_REVIEW"]
        if review:
            review_names = ", ".join([e.criterion_name for e in review])
            findings.append(f"⚠ Requires Review: {review_names}")
        
        # Find low confidence extractions
        low_conf = [e for e in criterion_evaluations if e.confidence < 0.7]
        if low_conf:
            findings.append(f"⚠ {len(low_conf)} fields have low extraction confidence")
        
        return findings
    
    def _generate_recommendations(
        self,
        evaluation_result: BidderEvaluationResult
    ) -> List[str]:
        """Generate recommendations based on evaluation"""
        recommendations = []
        
        decision = evaluation_result.final_decision.value
        
        if decision == "ELIGIBLE":
            recommendations.append("✔ Bidder meets all eligibility criteria")
            recommendations.append("→ Proceed to technical/financial evaluation")
        
        elif decision == "NOT_ELIGIBLE":
            failed = [
                e for e in evaluation_result.criterion_evaluations
                if e.status.value == "NOT_ELIGIBLE"
            ]
            if failed:
                reasons = ", ".join([e.criterion_name for e in failed])
                recommendations.append(f"❌ Bidder does not meet: {reasons}")
                recommendations.append("→ Recommend rejection")
        
        elif decision == "MANUAL_REVIEW":
            review_items = [
                e for e in evaluation_result.criterion_evaluations
                if e.status.value == "MANUAL_REVIEW"
            ]
            if review_items:
                items = ", ".join([e.criterion_name for e in review_items])
                recommendations.append(f"⚠ Manual verification needed for: {items}")
                recommendations.append("→ Send clarification request to bidder")
                recommendations.append("→ Allow bidder to provide additional documentation")
        
        return recommendations
    
    def generate_report(
        self,
        evaluation_result: BidderEvaluationResult
    ) -> str:
        """Generate human-readable report"""
        explanation = self.generate_explanation(evaluation_result)
        
        report = f"""
╔════════════════════════════════════════════════════════════════╗
║           TENDER EVALUATION REPORT                             ║
╚════════════════════════════════════════════════════════════════╝

Bidder: {explanation['bidder_name']}
Tender ID: {explanation['tender_id']}
Audit ID: {explanation['audit_id']}
Timestamp: {explanation['timestamp']}

FINAL DECISION: {explanation['final_decision']}
Overall Confidence: {explanation['confidence']}

────────────────────────────────────────────────────────────────
CRITERIA EVALUATION
────────────────────────────────────────────────────────────────
"""
        
        for criterion in explanation['criteria_breakdown']:
            report += f"\n{criterion['status_symbol']} {criterion['criterion_name']}\n"
            report += f"   Status: {criterion['status']}\n"
            report += f"   Confidence: {criterion['confidence']}\n"
            report += f"   Reason: {criterion['reason']}\n"
        
        report += f"""
────────────────────────────────────────────────────────────────
KEY FINDINGS
────────────────────────────────────────────────────────────────
"""
        for finding in explanation['key_findings']:
            report += f"• {finding}\n"
        
        report += f"""
────────────────────────────────────────────────────────────────
RECOMMENDATIONS
────────────────────────────────────────────────────────────────
"""
        for rec in explanation['recommendations']:
            report += f"• {rec}\n"
        
        report += "\n╚════════════════════════════════════════════════════════════════╝\n"
        
        return report
