"""
Main entry point for the Tender Evaluation System
"""
from src.document_processor import DocumentProcessor
from src.criteria_extractor import CriteriaExtractor
from src.bidder_parser import BidderParser
from src.evaluation_engine import EvaluationEngine
from src.explainability import ExplainabilityEngine
from src.audit_logger import AuditLogger


class TenderEvaluator:
    """Main orchestrator for tender evaluation"""
    
    def __init__(self):
        """Initialize all components"""
        self.doc_processor = DocumentProcessor()
        self.criteria_extractor = CriteriaExtractor()
        self.bidder_parser = BidderParser()
        self.evaluation_engine = EvaluationEngine()
        self.explainability = ExplainabilityEngine()
        self.audit_logger = AuditLogger()
    
    def evaluate_bidder(
        self,
        tender_doc_path: str,
        bidder_doc_path: str,
        bidder_name: str,
        tender_id: str
    ):
        """
        Complete evaluation pipeline
        """
        print(f"\n{'='*60}")
        print(f"Evaluating: {bidder_name}")
        print(f"Tender: {tender_id}")
        print(f"{'='*60}\n")
        
        # Step 1: Process tender document
        print("[1/5] Processing tender document...")
        tender_text, tender_conf, tender_pages = self.doc_processor.process_document(
            tender_doc_path
        )
        print(f"✓ Extracted {tender_pages} pages (confidence: {tender_conf:.0%})")
        
        # Step 2: Extract criteria
        print("\n[2/5] Extracting eligibility criteria...")
        tender_doc = self.criteria_extractor.extract_criteria(tender_text, tender_id)
        print(f"✓ Found {len(tender_doc.criteria)} criteria")
        for crit in tender_doc.criteria:
            print(f"  - {crit.name} (Required: {crit.required})")
        
        # Step 3: Process bidder document
        print("\n[3/5] Processing bidder submission...")
        bidder_text, bidder_conf, _ = self.doc_processor.process_document(
            bidder_doc_path
        )
        print(f"✓ Extracted bidder document (confidence: {bidder_conf:.0%})")
        
        # Step 4: Parse bidder submission
        print("\n[4/5] Parsing bidder information...")
        bidder_submission = self.bidder_parser.parse_submission(
            bidder_name,
            bidder_text,
            bidder_doc_path
        )
        print(f"✓ Extracted {len(bidder_submission.extracted_fields)} fields")
        for field, value in bidder_submission.extracted_fields.items():
            print(f"  - {field}: {value}")
        
        # Step 5: Evaluate
        print("\n[5/5] Evaluating eligibility...")
        evaluation_result = self.evaluation_engine.evaluate_bidder(
            tender_doc,
            bidder_submission
        )
        print(f"✓ Decision: {evaluation_result.final_decision.value}")
        print(f"✓ Confidence: {evaluation_result.overall_confidence:.0%}")
        
        # Log evaluation
        self.audit_logger.log_evaluation(evaluation_result)
        
        # Generate explanation
        print("\n" + "="*60)
        report = self.explainability.generate_report(evaluation_result)
        print(report)
        
        return evaluation_result
    
    def get_audit_trail(self, tender_id: str):
        """Retrieve audit trail for tender"""
        return self.audit_logger.generate_audit_report(tender_id)


def main():
    """Demo execution"""
    evaluator = TenderEvaluator()
    
    # Example usage (requires actual documents)
    print("\n🚀 AI-Powered Tender Evaluation System")
    print("Version 1.0 - Core System\n")
    
    print("System initialized with:")
    print("✓ Document Processor (PDF, Images)")
    print("✓ Criteria Extractor")
    print("✓ Bidder Parser")
    print("✓ Evaluation Engine")
    print("✓ Explainability Layer")
    print("✓ Audit Logger")
    
    print("\nTo evaluate a bidder, use:")
    print("""
    evaluator = TenderEvaluator()
    result = evaluator.evaluate_bidder(
        tender_doc_path="path/to/tender.pdf",
        bidder_doc_path="path/to/bidder_submission.pdf",
        bidder_name="ABC Pvt Ltd",
        tender_id="TENDER_2024_001"
    )
    """)


if __name__ == "__main__":
    main()
