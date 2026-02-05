"""
Escalation log for tracking human approvals.
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

from ..types import AgentRole, EscalationRequest, EscalationReason


class EscalationStatus(str, Enum):
    """Status of an escalation request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class EscalationEntry:
    """An escalation entry with status tracking."""
    request: EscalationRequest
    status: EscalationStatus = EscalationStatus.PENDING
    resolution_notes: str = ""
    resolved_at: Optional[datetime] = None


class EscalationLog:
    """
    Log for escalation requests requiring human approval.

    Tracks:
    - Pending escalations
    - Approved/rejected decisions
    - Resolution history
    """

    def __init__(self, persist_path: Optional[Path] = None):
        self._entries: List[EscalationEntry] = []
        self._persist_path = persist_path

        if persist_path and persist_path.exists():
            self._load()

    def create(
        self,
        reason: EscalationReason,
        what: str,
        why: str,
        risk: str,
        mitigation: str,
        requested_by: AgentRole,
    ) -> EscalationEntry:
        """Create a new escalation request."""
        request = EscalationRequest(
            reason=reason,
            what=what,
            why=why,
            risk=risk,
            mitigation=mitigation,
            requested_by=requested_by,
        )

        entry = EscalationEntry(request=request)
        self._entries.append(entry)

        if self._persist_path:
            self._persist()

        return entry

    def approve(
        self,
        index: int,
        approver: str,
        notes: str = "",
    ) -> bool:
        """Approve an escalation."""
        if 0 <= index < len(self._entries):
            entry = self._entries[index]
            if entry.status == EscalationStatus.PENDING:
                entry.status = EscalationStatus.APPROVED
                entry.request.approved_by = approver
                entry.request.approval_timestamp = datetime.utcnow()
                entry.resolution_notes = notes
                entry.resolved_at = datetime.utcnow()

                if self._persist_path:
                    self._persist()
                return True
        return False

    def reject(
        self,
        index: int,
        rejector: str,
        notes: str = "",
    ) -> bool:
        """Reject an escalation."""
        if 0 <= index < len(self._entries):
            entry = self._entries[index]
            if entry.status == EscalationStatus.PENDING:
                entry.status = EscalationStatus.REJECTED
                entry.request.approved_by = rejector  # Reusing field for rejector
                entry.resolution_notes = notes
                entry.resolved_at = datetime.utcnow()

                if self._persist_path:
                    self._persist()
                return True
        return False

    def get_pending(self) -> List[EscalationEntry]:
        """Get all pending escalations."""
        return [e for e in self._entries if e.status == EscalationStatus.PENDING]

    def get_approved(self) -> List[EscalationEntry]:
        """Get all approved escalations."""
        return [e for e in self._entries if e.status == EscalationStatus.APPROVED]

    def get_rejected(self) -> List[EscalationEntry]:
        """Get all rejected escalations."""
        return [e for e in self._entries if e.status == EscalationStatus.REJECTED]

    def get_by_reason(self, reason: EscalationReason) -> List[EscalationEntry]:
        """Get escalations by reason."""
        return [e for e in self._entries if e.request.reason == reason]

    def get_by_agent(self, agent: AgentRole) -> List[EscalationEntry]:
        """Get escalations by requesting agent."""
        return [e for e in self._entries if e.request.requested_by == agent]

    def _persist(self) -> None:
        """Persist log to file."""
        if not self._persist_path:
            return

        data = [
            {
                "request": {
                    "reason": e.request.reason.value if hasattr(e.request.reason, 'value') else str(e.request.reason),
                    "what": e.request.what,
                    "why": e.request.why,
                    "risk": e.request.risk,
                    "mitigation": e.request.mitigation,
                    "requested_by": e.request.requested_by.value,
                    "timestamp": e.request.timestamp.isoformat(),
                    "approved_by": e.request.approved_by,
                    "approval_timestamp": e.request.approval_timestamp.isoformat() if e.request.approval_timestamp else None,
                },
                "status": e.status.value,
                "resolution_notes": e.resolution_notes,
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
            }
            for e in self._entries
        ]

        self._persist_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        """Load log from file."""
        if not self._persist_path or not self._persist_path.exists():
            return

        try:
            data = json.loads(self._persist_path.read_text())
            self._entries = []

            for d in data:
                req = d["request"]
                request = EscalationRequest(
                    reason=req["reason"],
                    what=req["what"],
                    why=req["why"],
                    risk=req["risk"],
                    mitigation=req["mitigation"],
                    requested_by=AgentRole(req["requested_by"]),
                    timestamp=datetime.fromisoformat(req["timestamp"]),
                    approved_by=req.get("approved_by"),
                    approval_timestamp=datetime.fromisoformat(req["approval_timestamp"]) if req.get("approval_timestamp") else None,
                )

                entry = EscalationEntry(
                    request=request,
                    status=EscalationStatus(d["status"]),
                    resolution_notes=d.get("resolution_notes", ""),
                    resolved_at=datetime.fromisoformat(d["resolved_at"]) if d.get("resolved_at") else None,
                )
                self._entries.append(entry)

        except (json.JSONDecodeError, KeyError):
            self._entries = []

    def export_pending(self) -> List[Dict]:
        """Export pending escalations for display."""
        return [
            {
                "index": i,
                "reason": e.request.reason.value if hasattr(e.request.reason, 'value') else str(e.request.reason),
                "what": e.request.what,
                "why": e.request.why,
                "risk": e.request.risk,
                "mitigation": e.request.mitigation,
                "requested_by": e.request.requested_by.value,
                "timestamp": e.request.timestamp.isoformat(),
            }
            for i, e in enumerate(self._entries)
            if e.status == EscalationStatus.PENDING
        ]

    def clear_resolved(self) -> int:
        """Clear resolved entries, returns count cleared."""
        original_count = len(self._entries)
        self._entries = [e for e in self._entries if e.status == EscalationStatus.PENDING]
        cleared = original_count - len(self._entries)

        if self._persist_path:
            self._persist()

        return cleared

    @property
    def pending_count(self) -> int:
        """Get pending escalation count."""
        return len(self.get_pending())

    def get_stats(self) -> Dict:
        """Get escalation statistics."""
        by_reason: Dict[str, int] = {}
        for e in self._entries:
            reason = e.request.reason.value if hasattr(e.request.reason, 'value') else str(e.request.reason)
            by_reason[reason] = by_reason.get(reason, 0) + 1

        return {
            "total": len(self._entries),
            "pending": len(self.get_pending()),
            "approved": len(self.get_approved()),
            "rejected": len(self.get_rejected()),
            "by_reason": by_reason,
        }
