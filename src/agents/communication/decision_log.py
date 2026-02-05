"""
Decision log for audit trail.
"""

from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from ..types import AgentRole, DecisionLogEntry


class DecisionLog:
    """
    Audit log for all agent decisions.

    Provides:
    - Append-only log of decisions
    - Queryable by agent, task, time
    - Persistence to file
    """

    def __init__(self, persist_path: Optional[Path] = None):
        self._entries: List[DecisionLogEntry] = []
        self._persist_path = persist_path

        if persist_path and persist_path.exists():
            self._load()

    def log(
        self,
        decision_id: str,
        task_id: str,
        agent: AgentRole,
        decision: str,
        rationale: str,
        alternatives: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
    ) -> DecisionLogEntry:
        """Log a decision."""
        entry = DecisionLogEntry(
            decision_id=decision_id,
            task_id=task_id,
            agent=agent,
            decision=decision,
            rationale=rationale,
            alternatives_considered=alternatives or [],
            risks_acknowledged=risks or [],
        )

        self._entries.append(entry)

        if self._persist_path:
            self._persist()

        return entry

    def get_by_task(self, task_id: str) -> List[DecisionLogEntry]:
        """Get all decisions for a task."""
        return [e for e in self._entries if e.task_id == task_id]

    def get_by_agent(self, agent: AgentRole) -> List[DecisionLogEntry]:
        """Get all decisions by an agent."""
        return [e for e in self._entries if e.agent == agent]

    def get_by_time_range(
        self,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> List[DecisionLogEntry]:
        """Get decisions in a time range."""
        end = end or datetime.utcnow()
        return [
            e for e in self._entries
            if start <= e.timestamp <= end
        ]

    def get_recent(self, limit: int = 50) -> List[DecisionLogEntry]:
        """Get most recent decisions."""
        return self._entries[-limit:]

    def search(self, query: str) -> List[DecisionLogEntry]:
        """Search decisions by text."""
        query_lower = query.lower()
        return [
            e for e in self._entries
            if query_lower in e.decision.lower()
            or query_lower in e.rationale.lower()
        ]

    def get_vetoes(self) -> List[DecisionLogEntry]:
        """Get all veto decisions."""
        return [
            e for e in self._entries
            if "veto" in e.decision.lower()
        ]

    def get_escalations(self) -> List[DecisionLogEntry]:
        """Get all escalation decisions."""
        return [
            e for e in self._entries
            if "escalat" in e.decision.lower()
        ]

    def _persist(self) -> None:
        """Persist log to file."""
        if not self._persist_path:
            return

        data = [
            {
                "decision_id": e.decision_id,
                "task_id": e.task_id,
                "agent": e.agent.value,
                "decision": e.decision,
                "rationale": e.rationale,
                "timestamp": e.timestamp.isoformat(),
                "alternatives_considered": e.alternatives_considered,
                "risks_acknowledged": e.risks_acknowledged,
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
            self._entries = [
                DecisionLogEntry(
                    decision_id=d["decision_id"],
                    task_id=d["task_id"],
                    agent=AgentRole(d["agent"]),
                    decision=d["decision"],
                    rationale=d["rationale"],
                    timestamp=datetime.fromisoformat(d["timestamp"]),
                    alternatives_considered=d.get("alternatives_considered", []),
                    risks_acknowledged=d.get("risks_acknowledged", []),
                )
                for d in data
            ]
        except (json.JSONDecodeError, KeyError):
            self._entries = []

    def export(self) -> List[Dict]:
        """Export log as list of dicts."""
        return [
            {
                "decision_id": e.decision_id,
                "task_id": e.task_id,
                "agent": e.agent.value,
                "decision": e.decision,
                "rationale": e.rationale,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in self._entries
        ]

    def clear(self) -> int:
        """Clear all entries, returns count cleared."""
        count = len(self._entries)
        self._entries.clear()
        if self._persist_path:
            self._persist()
        return count

    @property
    def count(self) -> int:
        """Get entry count."""
        return len(self._entries)

    def get_stats(self) -> Dict:
        """Get log statistics."""
        by_agent = {}
        for e in self._entries:
            by_agent[e.agent.value] = by_agent.get(e.agent.value, 0) + 1

        return {
            "total_decisions": self.count,
            "by_agent": by_agent,
            "vetoes": len(self.get_vetoes()),
            "escalations": len(self.get_escalations()),
        }
