"""
Parse bidder submission documents
"""
from typing import Dict, Any
from datetime import datetime
from src.models import BidderSubmission


class BidderParser:
    """Parse and extract information from bidder submissions"""
    
    def __init__(self):
        """Initialize bidder parser"""
        self.field_patterns = {
            "turnover": ["turnover", "revenue", "annual revenue"],
            "iso": ["iso", "certification"],
            "experience": ["experience", "years"],
            "gst": ["gst", "tax id"],
            "pan": ["pan", "permanent account"]
        }
    
    def parse_submission(
        self,
        bidder_name: str,
        submission_text: str,
        source_document: str
    ) -> BidderSubmission:
        """
        Parse bidder submission and extract fields
        """
        extracted_fields = self._extract_fields(submission_text)
        
        return BidderSubmission(
            bidder_name=bidder_name,
            submission_date=datetime.now(),
            extracted_fields=extracted_fields,
            raw_text=submission_text,
            extraction_confidence=0.8,
            source_document=source_document
        )
    
    def _extract_fields(self, text: str) -> Dict[str, Any]:
        """Extract structured fields from submission text"""
        fields = {}
        text_lower = text.lower()
        
        # Extract turnover
        turnover = self._extract_currency(text, "turnover")
        if turnover:
            fields["turnover"] = turnover
        
        # Extract experience
        experience = self._extract_number(text, "experience")
        if experience:
            fields["experience_years"] = experience
        
        # Extract GST
        gst = self._extract_gst(text)
        if gst:
            fields["gst_number"] = gst
        
        # Extract PAN
        pan = self._extract_pan(text)
        if pan:
            fields["pan_number"] = pan
        
        # Extract ISO certifications
        iso_certs = self._extract_iso(text)
        if iso_certs:
            fields["iso_certifications"] = iso_certs
        
        return fields
    
    def _extract_currency(self, text: str, keyword: str) -> Dict[str, Any]:
        """Extract currency values"""
        # Simple pattern matching for currency
        import re
        pattern = r'₹\s*([\d,]+(?:\.\d+)?)\s*(?:Cr|Lakh|L)?'
        matches = re.findall(pattern, text)
        
        if matches:
            return {
                "value": matches[0],
                "currency": "INR",
                "confidence": 0.85
            }
        return None
    
    def _extract_number(self, text: str, keyword: str) -> int:
        """Extract numeric values"""
        import re
        pattern = r'(\d+)\s*(?:years?|yrs?)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        if matches:
            return int(matches[0])
        return None
    
    def _extract_gst(self, text: str) -> str:
        """Extract GST number"""
        import re
        # GST format: 2 digits state + 10 digit PAN + 1 check digit + Z
        pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z0-9]{3}'
        matches = re.findall(pattern, text)
        
        return matches[0] if matches else None
    
    def _extract_pan(self, text: str) -> str:
        """Extract PAN number"""
        import re
        # PAN format: 5 letters + 4 digits + 1 letter
        pattern = r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
        matches = re.findall(pattern, text)
        
        return matches[0] if matches else None
    
    def _extract_iso(self, text: str) -> list:
        """Extract ISO certifications"""
        import re
        iso_pattern = r'ISO\s*(\d{4}(?::\d{4})?)'
        matches = re.findall(iso_pattern, text, re.IGNORECASE)
        
        return matches if matches else []
