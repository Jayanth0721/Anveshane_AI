"""
Automated verification script for Live Contradiction Engine
Run: python scratch/test_contradiction.py
"""
import sys
from datetime import datetime
sys.path.insert(0, ".")

from src.models import BidderSubmission
from src.contradiction_engine import ContradictionEngine

def run_tests():
    print("=" * 60)
    print("Running Contradiction Engine Automated Tests...")
    print("=" * 60)

    engine = ContradictionEngine()

    # 1. TEST CASE A: Completely Valid Bid (No Contradictions)
    print("\n[Test 1] Testing a completely valid bid (no contradictions)...")
    valid_submission = BidderSubmission(
        bidder_name="Apex Global Ltd.",
        submission_date=datetime.now(),
        extracted_fields={
            "turnover": {"value": "45.0", "currency": "INR", "confidence": 0.9},
            "experience_years": 12,
            "gst_number": "29ABCDE1234F1Z5",
            "pan_number": "ABCDE1234F"
        },
        raw_text="Established in 2010. We have 12 years of operational experience. Audited turnover is Rs. 45.0 Cr.",
        extraction_confidence=0.9,
        source_document="apex_proposal.docx"
    )
    conflicts_a = engine.detect_contradictions(valid_submission)
    print(f"  -> Detected {len(conflicts_a)} contradictions.")
    if conflicts_a:
        for c in conflicts_a:
            safe_msg = str(c.get("message")).replace('₹', 'Rs.')
            safe_ev = str(c.get("evidence")).replace('₹', 'Rs.')
            print(f"     * Debug Contradiction: type={c.get('type')}, field={c.get('field')}, msg={safe_msg}, ev={safe_ev}")
    assert len(conflicts_a) == 0, "Expected 0 contradictions for a valid bid"
    print("  [OK] Test 1 Passed!")

    # 2. TEST CASE B: Tax ID Mismatch
    print("\n[Test 2] Testing Tax ID Mismatch (GSTIN vs PAN)...")
    tax_conflict_submission = BidderSubmission(
        bidder_name="Apex Global Ltd.",
        submission_date=datetime.now(),
        extracted_fields={
            "gst_number": "29ABCDE1234F1Z5", # embedded PAN is ABCDE1234F
            "pan_number": "XYZAB9999C"       # mismatch!
        },
        raw_text="GSTIN: 29ABCDE1234F1Z5, PAN: XYZAB9999C.",
        extraction_confidence=0.9,
        source_document="apex_proposal.docx"
    )
    conflicts_b = engine.detect_contradictions(tax_conflict_submission)
    print(f"  -> Detected {len(conflicts_b)} contradictions.")
    assert len(conflicts_b) == 1, "Expected 1 tax ID contradiction"
    safe_msg_b = str(conflicts_b[0]['message']).replace('₹', 'Rs.')
    print(f"  -> Error: {safe_msg_b}")
    assert conflicts_b[0]["type"] == "tax_id_mismatch", "Expected tax ID mismatch conflict type"
    print("  [OK] Test 2 Passed!")

    # 3. TEST CASE C: Turnover Discrepancy (Declared vs Audited)
    print("\n[Test 3] Testing Turnover Discrepancy...")
    turnover_conflict_submission = BidderSubmission(
        bidder_name="Apex Global Ltd.",
        submission_date=datetime.now(),
        extracted_fields={
            "turnover": {"value": "50.0", "currency": "INR", "confidence": 0.9} # claims Rs. 50 Cr
        },
        # Audited statement mentions Rs. 5.0 Cr (10x smaller!)
        raw_text="Company profile: We boast an annual turnover of Rs. 50.0 Cr. \nAudited financials page: The gross audited revenue for FY2025 is Rs. 5.0 Cr.",
        extraction_confidence=0.9,
        source_document="apex_proposal.docx"
    )
    conflicts_c = engine.detect_contradictions(turnover_conflict_submission)
    print(f"  -> Detected {len(conflicts_c)} contradictions.")
    assert len(conflicts_c) == 1, "Expected 1 turnover contradiction"
    safe_msg_c = str(conflicts_c[0]['message']).replace('₹', 'Rs.')
    print(f"  -> Error: {safe_msg_c}")
    assert conflicts_c[0]["type"] == "turnover_mismatch", "Expected turnover mismatch conflict type"
    print("  [OK] Test 3 Passed!")

    # 4. TEST CASE D: Experience chronology mismatch
    print("\n[Test 4] Testing Experience Chronology Mismatch...")
    experience_conflict_submission = BidderSubmission(
        bidder_name="Apex Global Ltd.",
        submission_date=datetime.now(),
        extracted_fields={
            "experience_years": 15 # Claims 15 years
        },
        # Estd in 2022 (max possible operational years in 2026 is 4)
        raw_text="The company was established in 2022. We possess 15 years of industry experience.",
        extraction_confidence=0.9,
        source_document="apex_proposal.docx"
    )
    conflicts_d = engine.detect_contradictions(experience_conflict_submission)
    print(f"  -> Detected {len(conflicts_d)} contradictions.")
    assert len(conflicts_d) == 1, "Expected 1 experience contradiction"
    print(f"  -> Error: {conflicts_d[0]['message']}")
    assert conflicts_d[0]["type"] == "experience_mismatch", "Expected experience mismatch conflict type"
    print("  [OK] Test 4 Passed!")

    print("\n" + "=" * 60)
    print("SUCCESS: ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
