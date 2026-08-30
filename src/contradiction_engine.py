"""
Live Contradiction Engine for identifying inconsistencies within bidder submissions
"""
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.models import BidderSubmission


class ContradictionEngine:
    """Engine for detecting contradictions in bidder documents"""

    def __init__(self):
        """Initialize contradiction engine with search patterns"""
        # Patterns for finding founding/incorporation years
        self.inc_patterns = [
            r'(?:incorporated|established|founded|started|registered|incorporation|formation)\b[^.]{0,30}\b(19\d{2}|20\d{2})\b',
            r'\b(?:inception|setup)\b[^.]{0,30}\b(19\d{2}|20\d{2})\b',
            r'\b(?:estd\.?|est\b\.?)[^.]{0,20}\b(19\d{2}|20\d{2})\b'
        ]

    def detect_contradictions(self, bidder_submission: BidderSubmission) -> List[Dict[str, Any]]:
        """
        Orchestrate all contradiction checks on the bidder submission.
        Returns a list of contradiction details.
        """
        contradictions = []

        # 1. Tax ID Mismatch Check
        tax_id_conflict = self._check_tax_ids(bidder_submission.extracted_fields)
        if tax_id_conflict:
            contradictions.append(tax_id_conflict)

        # 2. Turnover Discrepancy Check
        turnover_conflict = self._check_turnover(
            bidder_submission.extracted_fields, 
            bidder_submission.raw_text
        )
        if turnover_conflict:
            contradictions.append(turnover_conflict)

        # 3. Experience vs Incorporation Year Check
        experience_conflict = self._check_experience(
            bidder_submission.extracted_fields,
            bidder_submission.raw_text
        )
        if experience_conflict:
            contradictions.append(experience_conflict)

        return contradictions

    def _check_tax_ids(self, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Verify that the PAN number matches the embedded PAN inside the GSTIN.
        GSTIN format: StateCode(2) + PAN(10) + EntityCode(1) + CheckDigit(1) + Character(1)
        """
        gst = fields.get("gst_number")
        pan = fields.get("pan_number")

        if not gst or not pan:
            return None

        # Normalize strings
        gst_clean = re.sub(r'\s+', '', str(gst)).upper()
        pan_clean = re.sub(r'\s+', '', str(pan)).upper()

        if len(gst_clean) < 12 or len(pan_clean) < 10:
            return None

        # Extract the middle 10-char PAN sequence from GSTIN (index 2 to 12)
        gst_pan = gst_clean[2:12]

        if gst_pan != pan_clean:
            return {
                "type": "tax_id_mismatch",
                "severity": "critical",
                "message": f"Tax ID Discrepancy: Extracted PAN is '{pan_clean}', but your GSTIN '{gst_clean}' contains PAN '{gst_pan}'. They must match.",
                "evidence": f"PAN in GSTIN: {gst_pan} vs declared PAN: {pan_clean}",
                "field": "GST / PAN Registration"
            }

        return None

    def _check_turnover(self, fields: Dict[str, Any], text: str) -> Optional[Dict[str, Any]]:
        """
        Check if the declared turnover matches financial values mentioned elsewhere in the text.
        We look for currency figures associated with turnover / revenue.
        """
        # Get primary extracted turnover value
        primary_val = None
        turnover_field = fields.get("turnover")
        
        if turnover_field is None:
            return None

        if isinstance(turnover_field, dict):
            primary_val = turnover_field.get("value")
        else:
            primary_val = turnover_field

        if not primary_val:
            return None

        try:
            # Normalize primary value to float
            primary_num = float(str(primary_val).replace(',', ''))
        except ValueError:
            return None

        # Scan raw text for all other currency occurrences near turnover keywords
        text_lower = text.lower()
        keyword_patterns = ["turnover", "revenue", "receipts", "gross sales", "annual revenue"]
        
        # Regex to find numbers representing money (e.g. ₹50 Cr, INR 5 Crore, 10cr, 50,00,000)
        currency_pattern = r'(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore|lakh|l|million|m)?'
        
        detected_values = []
        
        # Find index of turnover keywords and extract money values in their vicinity
        for kw in keyword_patterns:
            for match in re.finditer(re.escape(kw), text_lower):
                start = max(0, match.start() - 60)
                end = min(len(text), match.end() + 60)
                context = text[start:end]
                
                # Search for currency in this context window
                for cur_match in re.finditer(currency_pattern, context, re.IGNORECASE):
                    matched_str = cur_match.group(0).lower()
                    has_prefix = any(p in matched_str for p in ["₹", "rs", "inr"])
                    has_suffix = any(s in matched_str for s in ["cr", "crore", "lakh", "million"])
                    
                    if not (has_prefix or has_suffix):
                        # Skip raw numbers like years (2010) or counts (12)
                        continue
                        
                    val_str = cur_match.group(1).replace(',', '')
                    try:
                        val = float(val_str)
                        if val <= 0:
                            continue
                        
                        # Scale value based on suffix in context
                        context_segment = context[cur_match.start():cur_match.end() + 15].lower()
                        is_cr = "cr" in context_segment or "crore" in context_segment
                        is_lakh = "lakh" in context_segment or "l " in context_segment or "lakhs" in context_segment
                        
                        scale_factor = 1.0
                        if is_cr:
                            # Primary values are usually represented in Crore if they are single digits (e.g. 50 or 8)
                            scale_factor = 1.0
                        elif is_lakh:
                            # Convert Lakhs to Crores (1 Lakh = 0.01 Crore)
                            scale_factor = 0.01
                        
                        scaled_val = val * scale_factor
                        
                        # Avoid duplicates
                        if scaled_val not in detected_values:
                            detected_values.append(scaled_val)
                    except ValueError:
                        continue

        # If we have multiple turnover figures, compare them
        for other_val in detected_values:
            # Skip if they are extremely close (less than 2% difference) or identical
            if abs(primary_num - other_val) < 0.05 * primary_num:
                continue
                
            # If the difference is significant (e.g. one is ₹50 Cr and the other is ₹5 Cr), flag it!
            # Example: 10x discrepancy (declared vs audited)
            ratio = max(primary_num, other_val) / max(0.01, min(primary_num, other_val))
            if ratio >= 1.5:  # more than 50% discrepancy
                return {
                    "type": "turnover_mismatch",
                    "severity": "high",
                    "message": f"Financial Discrepancy: Primary turnover of Rs. {primary_num:.1f} Cr contradicts other audited figures of Rs. {other_val:.1f} Cr extracted from your financial text.",
                    "evidence": f"Declared: Rs. {primary_num:.1f} Cr vs Audited/Alternative: Rs. {other_val:.1f} Cr",
                    "field": "Annual Turnover"
                }

        return None

    def _check_experience(self, fields: Dict[str, Any], text: str) -> Optional[Dict[str, Any]]:
        """
        Verify that years of experience is mathematically possible given the founding year.
        """
        experience = fields.get("experience_years")
        if experience is None:
            return None

        try:
            exp_years = int(experience)
        except ValueError:
            return None

        # Search for founding/incorporation year in the text
        inc_year = None
        for pattern in self.inc_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    inc_year = int(matches[0])
                    break
                except ValueError:
                    continue

        if not inc_year:
            return None

        # Current year of operation (2026 as per local system time metadata, or datetime.now().year)
        current_year = datetime.now().year
        max_possible_years = current_year - inc_year

        # Give a 1-year buffer for overlapping dates/fiscal years
        if exp_years > max_possible_years + 1:
            return {
                "type": "experience_mismatch",
                "severity": "medium",
                "message": f"Timeline Chronology Mismatch: Bidder claims {exp_years} years of operational experience, but documents indicate the company was established in {inc_year} (maximum possible experience is {max_possible_years} years).",
                "evidence": f"Claimed Experience: {exp_years} yrs vs Company Age: {max_possible_years} yrs (Estd. {inc_year})",
                "field": "Years of Experience"
            }

        return None
