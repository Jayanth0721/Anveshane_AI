"""
Audit logging and trail management
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from src.models import AuditLog, BidderEvaluationResult, DecisionStatus


class AuditLogger:
    """Manage audit trails for full traceability"""
    
    def __init__(self, log_dir: str = "audit_logs"):
        """Initialize audit logger"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
    
    def log_evaluation(
        self,
        evaluation_result: BidderEvaluationResult,
        user_id: Optional[str] = None
    ) -> AuditLog:
        """Log evaluation decision"""
        
        audit_log = AuditLog(
            timestamp=datetime.now(),
            action="EVALUATION",
            user_id=user_id,
            bidder_name=evaluation_result.bidder_name,
            tender_id=evaluation_result.tender_id,
            decision=evaluation_result.final_decision,
            reason=evaluation_result.summary,
            override=False,
            audit_id=evaluation_result.audit_id
        )
        
        self._write_log(audit_log)
        return audit_log
    
    def log_override(
        self,
        bidder_name: str,
        tender_id: str,
        original_decision: DecisionStatus,
        new_decision: DecisionStatus,
        reason: str,
        user_id: str,
        audit_id: str
    ) -> AuditLog:
        """Log decision override by human reviewer"""
        
        audit_log = AuditLog(
            timestamp=datetime.now(),
            action=f"OVERRIDE: {original_decision.value} → {new_decision.value}",
            user_id=user_id,
            bidder_name=bidder_name,
            tender_id=tender_id,
            decision=new_decision,
            reason=reason,
            override=True,
            audit_id=audit_id
        )
        
        self._write_log(audit_log)
        return audit_log
    
    def log_clarification_request(
        self,
        bidder_name: str,
        tender_id: str,
        missing_fields: list,
        audit_id: str
    ) -> AuditLog:
        """Log clarification request sent to bidder"""
        
        audit_log = AuditLog(
            timestamp=datetime.now(),
            action="CLARIFICATION_REQUEST",
            user_id=None,
            bidder_name=bidder_name,
            tender_id=tender_id,
            decision=DecisionStatus.MANUAL_REVIEW,
            reason=f"Clarification requested for: {', '.join(missing_fields)}",
            override=False,
            audit_id=audit_id
        )
        
        self._write_log(audit_log)
        return audit_log
    
    def _write_log(self, audit_log: AuditLog) -> None:
        """Write audit log to file"""
        
        # Create tender-specific log file
        log_file = self.log_dir / f"{audit_log.tender_id}_audit.jsonl"
        
        # Append log entry
        with open(log_file, 'a') as f:
            f.write(audit_log.model_dump_json() + "\n")
    
    def log_event(self, tender_id: str, action: str, actor_id: str, details: str, confidence_score: float = None):
        """Log a generic system event"""
        import uuid
        audit_log = AuditLog(
            timestamp=datetime.now(),
            action=action,
            user_id=actor_id,
            bidder_name="SYSTEM",
            tender_id=tender_id,
            decision=DecisionStatus.MANUAL_REVIEW, # placeholder
            reason=details + (f" (Score: {confidence_score:.2f})" if confidence_score else ""),
            override=False,
            audit_id=str(uuid.uuid4())
        )
        self._write_log(audit_log)
        return audit_log

    def get_audit_trail(self, tender_id: str) -> list:
        """Retrieve complete audit trail for a tender"""
        
        log_file = self.log_dir / f"{tender_id}_audit.jsonl"
        
        if not log_file.exists():
            return []
        
        trail = []
        with open(log_file, 'r') as f:
            for line in f:
                if line.strip():
                    trail.append(json.loads(line))
        
        return trail
    
    def get_bidder_history(self, bidder_name: str) -> list:
        """Get evaluation history for a bidder"""
        
        history = []
        
        for log_file in self.log_dir.glob("*_audit.jsonl"):
            with open(log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("bidder_name") == bidder_name:
                            history.append(entry)
        
        return sorted(history, key=lambda x: x["timestamp"])

    def get_all_logs(self, limit: int = 50) -> list:
        """Retrieve all audit logs across all tenders, sorted by timestamp descending"""
        all_logs = []
        for log_file in self.log_dir.glob("*_audit.jsonl"):
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            all_logs.append(json.loads(line))
            except Exception:
                continue
        
        # Sort by timestamp descending
        all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_logs[:limit]

    
    def generate_audit_report(self, tender_id: str) -> str:
        """Generate audit report for tender"""
        
        trail = self.get_audit_trail(tender_id)
        
        if not trail:
            return f"No audit trail found for tender {tender_id}"
        
        report = f"""
╔════════════════════════════════════════════════════════════════╗
║           AUDIT TRAIL REPORT                                   ║
║           Tender ID: {tender_id:<45} ║
╚════════════════════════════════════════════════════════════════╝

Total Entries: {len(trail)}

────────────────────────────────────────────────────────────────
AUDIT LOG
────────────────────────────────────────────────────────────────
"""
        
        for entry in trail:
            report += f"\n[{entry['timestamp']}]\n"
            report += f"Action: {entry['action']}\n"
            report += f"Bidder: {entry['bidder_name']}\n"
            report += f"Decision: {entry['decision']}\n"
            report += f"Reason: {entry['reason']}\n"
            
            if entry.get('override'):
                report += f"User: {entry['user_id']} (OVERRIDE)\n"
            
            report += f"Audit ID: {entry['audit_id']}\n"
            report += "─" * 60 + "\n"
        
        report += "\n╚════════════════════════════════════════════════════════════════╝\n"
        
        return report
