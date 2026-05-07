"""
Extract eligibility criteria from tender documents
"""
from typing import List
from src.models import EligibilityCriterion, TenderDocument


class CriteriaExtractor:
    """Extract and parse eligibility criteria from tender documents"""
    
    def __init__(self):
        """Initialize criteria extractor"""
        # Common tender criteria patterns
        self.common_criteria = {
            "turnover": {
                "name": "Annual Turnover",
                "data_type": "currency",
                "required": True
            },
            "iso": {
                "name": "ISO Certification",
                "data_type": "text",
                "required": False
            },
            "experience": {
                "name": "Years of Experience",
                "data_type": "integer",
                "required": True
            },
            "gst": {
                "name": "GST Registration",
                "data_type": "text",
                "required": True
            },
            "pan": {
                "name": "PAN Registration",
                "data_type": "text",
                "required": True
            }
        }
    
    def extract_criteria(self, tender_text: str, tender_id: str) -> TenderDocument:
        """
        Extract criteria from tender document text
        """
        criteria = []
        criterion_id = 1
        
        # Simple pattern matching for common criteria
        for key, criterion_info in self.common_criteria.items():
            if self._find_criterion_in_text(tender_text, key):
                criteria.append(EligibilityCriterion(
                    criterion_id=f"CRIT_{criterion_id:03d}",
                    name=criterion_info["name"],
                    description=f"Bidder must meet {criterion_info['name']} requirement",
                    required=criterion_info["required"],
                    data_type=criterion_info["data_type"],
                    expected_value=None,
                    source_page=1
                ))
                criterion_id += 1
        
        # If no criteria found, add default ones
        if not criteria:
            criteria = self._get_default_criteria()
        
        return TenderDocument(
            tender_id=tender_id,
            title="Tender Document",
            criteria=criteria,
            raw_text=tender_text,
            extraction_confidence=0.85
        )
    
    def _find_criterion_in_text(self, text: str, keyword: str) -> bool:
        """Check if criterion keyword exists in text"""
        text_lower = text.lower()
        keywords = {
            "turnover": ["turnover", "revenue", "annual revenue"],
            "iso": ["iso", "certification"],
            "experience": ["experience", "years", "expertise"],
            "gst": ["gst", "tax", "registration"],
            "pan": ["pan", "permanent account"]
        }
        
        for kw in keywords.get(keyword, []):
            if kw in text_lower:
                return True
        return False
    
    def _get_default_criteria(self) -> List[EligibilityCriterion]:
        """Return default criteria for tender"""
        return [
            EligibilityCriterion(
                criterion_id="CRIT_001",
                name="Annual Turnover",
                description="Minimum annual turnover requirement",
                required=True,
                data_type="currency",
                expected_value=None,
                source_page=1
            ),
            EligibilityCriterion(
                criterion_id="CRIT_002",
                name="GST Registration",
                description="Valid GST registration required",
                required=True,
                data_type="text",
                expected_value=None,
                source_page=1
            ),
            EligibilityCriterion(
                criterion_id="CRIT_003",
                name="Years of Experience",
                description="Minimum years of relevant experience",
                required=True,
                data_type="integer",
                expected_value=None,
                source_page=1
            )
        ]
