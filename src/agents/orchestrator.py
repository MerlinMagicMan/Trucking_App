"""
Orchestrator - Coordinates the multi-agent development team.
"""

import uuid
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .types import (
    AgentRole, Task, TaskBreakdown, TaskStatus, Message,
    EscalationRequest, DecisionLogEntry, Module,
)
from .specialists import (
    TechLeadAgent,
    ProductGuardianAgent,
    ArchitectureObserverAgent,
    DatabaseArchitectAgent,
    BackendDevAgent,
    FrontendDevAgent,
    AlgorithmEngineerAgent,
    DevOpsEngineerAgent,
    QAEngineerAgent,
)
from .specialists.base import BaseAgent, AgentResponse


@dataclass
class OrchestratorState:
    """Current state of the orchestrator."""
    active_tasks: Dict[str, Task] = field(default_factory=dict)
    completed_tasks: List[Task] = field(default_factory=list)
    pending_escalations: List[EscalationRequest] = field(default_factory=list)
    decision_log: List[DecisionLogEntry] = field(default_factory=list)
    message_history: List[Message] = field(default_factory=list)


class Orchestrator:
    """
    Orchestrator coordinates the multi-agent development team.

    Workflow:
    1. Receive task from user/CLI
    2. Tech Lead breaks down task
    3. Product Guardian reviews (can VETO)
    4. Architecture Observer scans for systemic issues
    5. Specialists implement
    6. QA reviews (can block merge)
    """

    def __init__(self):
        self.state = OrchestratorState()

        # Initialize all agents
        self.agents: Dict[AgentRole, BaseAgent] = {
            AgentRole.TECH_LEAD: TechLeadAgent(),
            AgentRole.PRODUCT_GUARDIAN: ProductGuardianAgent(),
            AgentRole.ARCHITECTURE_OBSERVER: ArchitectureObserverAgent(),
            AgentRole.DATABASE_ARCHITECT: DatabaseArchitectAgent(),
            AgentRole.BACKEND_DEV: BackendDevAgent(),
            AgentRole.FRONTEND_DEV: FrontendDevAgent(),
            AgentRole.ALGORITHM_ENGINEER: AlgorithmEngineerAgent(),
            AgentRole.DEVOPS_ENGINEER: DevOpsEngineerAgent(),
            AgentRole.QA_ENGINEER: QAEngineerAgent(),
        }

        self.tech_lead = self.agents[AgentRole.TECH_LEAD]

    async def process_request(self, request: str) -> Dict:
        """
        Process a development request.

        This is the main entry point for new work.
        """
        print(f"\n{'='*60}")
        print(f"Processing request: {request}")
        print(f"{'='*60}\n")

        # Step 1: Tech Lead breaks down the task
        breakdown = await self.tech_lead.break_down_task(request)
        self._log_decision(
            task_id="INIT",
            agent=AgentRole.TECH_LEAD,
            decision=f"Task breakdown: {breakdown.type.value}",
            rationale=f"Module: {breakdown.module.value}, Tier: {breakdown.tier.value}",
        )

        # Step 2: Product Guardian review (for features)
        if breakdown.type.value == "feature":
            guardian_result = await self._get_guardian_approval(breakdown)
            if guardian_result.get("vetoed"):
                return {
                    "status": "vetoed",
                    "reason": guardian_result.get("reason"),
                    "requires_human_override": True,
                }
            breakdown.guardian_approved = True

        # Step 3: Check for escalation requirements
        if breakdown.escalation_required:
            escalation = self._create_escalation(breakdown)
            self.state.pending_escalations.append(escalation)
            return {
                "status": "escalation_required",
                "escalation": {
                    "reason": breakdown.escalation_reason.value if breakdown.escalation_reason else "Unknown",
                    "tasks": [t.description for t in breakdown.tasks],
                },
            }

        # Step 4: Architecture Observer scan
        arch_signals = await self._run_architecture_scan()
        if arch_signals.get("alerts"):
            print(f"⚠️  Architecture alerts: {arch_signals['alerts']}")

        # Step 5: Execute tasks in dependency order
        results = await self._execute_tasks(breakdown.tasks)

        # Step 6: Final QA gate
        qa_result = await self._run_qa_gate(results)

        return {
            "status": "completed" if qa_result["approved"] else "blocked",
            "breakdown": {
                "type": breakdown.type.value,
                "module": breakdown.module.value,
                "tier": breakdown.tier.value,
                "task_count": len(breakdown.tasks),
            },
            "results": results,
            "qa_result": qa_result,
            "decision_log": [
                {"agent": d.agent.value, "decision": d.decision}
                for d in self.state.decision_log[-10:]
            ],
        }

    async def _get_guardian_approval(self, breakdown: TaskBreakdown) -> Dict:
        """Get Product Guardian approval for feature placement."""
        guardian = self.agents[AgentRole.PRODUCT_GUARDIAN]

        message = Message(
            id=str(uuid.uuid4()),
            from_agent=AgentRole.TECH_LEAD,
            to_agent=AgentRole.PRODUCT_GUARDIAN,
            subject=breakdown.summary,
            content=f"Module: {breakdown.module.value}, Tier: {breakdown.tier.value}",
            priority="high",
            requires_response=True,
        )

        response = await guardian.handle_message(message)
        self.state.message_history.append(message)

        self._log_decision(
            task_id="GUARDIAN",
            agent=AgentRole.PRODUCT_GUARDIAN,
            decision=response.message,
            rationale=str(response.data) if response.data else "",
        )

        if not response.success and response.requires_escalation:
            return {
                "vetoed": True,
                "reason": response.message,
            }

        return {"vetoed": False}

    async def _run_architecture_scan(self) -> Dict:
        """Run Architecture Observer scan."""
        observer = self.agents[AgentRole.ARCHITECTURE_OBSERVER]

        signals = await observer.scan_codebase()

        alerts = [s for s in signals if s.severity.value == "alert"]
        warnings = [s for s in signals if s.severity.value == "warning"]

        self._log_decision(
            task_id="ARCH_SCAN",
            agent=AgentRole.ARCHITECTURE_OBSERVER,
            decision=f"Scan complete: {len(alerts)} alerts, {len(warnings)} warnings",
            rationale="; ".join([s.summary for s in alerts[:3]]),
        )

        return {
            "alerts": [s.summary for s in alerts],
            "warnings": [s.summary for s in warnings],
            "signal_count": len(signals),
        }

    async def _execute_tasks(self, tasks: List[Task]) -> List[Dict]:
        """Execute tasks in dependency order."""
        results = []
        completed_ids = set()

        # Simple topological execution (tasks with no dependencies first)
        remaining = list(tasks)

        while remaining:
            # Find tasks with all dependencies satisfied
            ready = [
                t for t in remaining
                if all(dep in completed_ids for dep in t.dependencies)
            ]

            if not ready:
                # Circular dependency or missing dependency
                print("⚠️  No ready tasks - possible circular dependency")
                break

            for task in ready:
                task.status = TaskStatus.IN_PROGRESS
                self.state.active_tasks[task.id] = task

                # Get the appropriate agent
                if task.assigned_to:
                    agent = self.agents.get(task.assigned_to)
                    if agent:
                        print(f"  → {task.assigned_to.value}: {task.description}")
                        response = await agent.process_task(task)

                        results.append({
                            "task_id": task.id,
                            "agent": task.assigned_to.value,
                            "success": response.success,
                            "message": response.message,
                        })

                        self._log_decision(
                            task_id=task.id,
                            agent=task.assigned_to,
                            decision=response.message,
                            rationale="Task execution",
                        )

                        if response.requires_escalation:
                            self.state.pending_escalations.append(
                                EscalationRequest(
                                    reason=response.escalation_reason or "Unknown",
                                    what=task.description,
                                    why=response.message,
                                    risk="See agent response",
                                    mitigation="Human review required",
                                    requested_by=task.assigned_to,
                                )
                            )

                task.status = TaskStatus.COMPLETED
                completed_ids.add(task.id)
                self.state.completed_tasks.append(task)
                del self.state.active_tasks[task.id]
                remaining.remove(task)

        return results

    async def _run_qa_gate(self, results: List[Dict]) -> Dict:
        """Run QA gate on completed work."""
        qa = self.agents[AgentRole.QA_ENGINEER]

        # QA reviews all results
        blocking_issues = []

        for result in results:
            if not result["success"]:
                blocking_issues.append(f"Task {result['task_id']} failed: {result['message']}")

        approved = len(blocking_issues) == 0

        self._log_decision(
            task_id="QA_GATE",
            agent=AgentRole.QA_ENGINEER,
            decision="APPROVED" if approved else "BLOCKED",
            rationale="; ".join(blocking_issues) if blocking_issues else "All checks passed",
        )

        return {
            "approved": approved,
            "blocking_issues": blocking_issues,
        }

    def _create_escalation(self, breakdown: TaskBreakdown) -> EscalationRequest:
        """Create an escalation request."""
        return EscalationRequest(
            reason=breakdown.escalation_reason or "Unknown",
            what=breakdown.summary,
            why=f"Task type: {breakdown.type.value}, Module: {breakdown.module.value}",
            risk="See breakdown details",
            mitigation="Human approval required before proceeding",
            requested_by=AgentRole.TECH_LEAD,
        )

    def _log_decision(
        self,
        task_id: str,
        agent: AgentRole,
        decision: str,
        rationale: str,
    ):
        """Log a decision for audit trail."""
        entry = DecisionLogEntry(
            decision_id=str(uuid.uuid4()),
            task_id=task_id,
            agent=agent,
            decision=decision,
            rationale=rationale,
        )
        self.state.decision_log.append(entry)

    async def audit_boundaries(self) -> Dict:
        """Run a full boundary audit."""
        print("\n🔍 Running boundary audit...\n")

        # Get Architecture Observer signals
        observer = self.agents[AgentRole.ARCHITECTURE_OBSERVER]
        signals = await observer.scan_codebase()

        # Categorize
        import_violations = [s for s in signals if s.observation_type == "import_violation"]
        decimal_violations = [s for s in signals if s.observation_type == "decimal_violation"]
        entitlement_issues = [s for s in signals if s.observation_type == "entitlement_bypass"]

        return {
            "import_violations": [s.summary for s in import_violations],
            "decimal_violations": [s.summary for s in decimal_violations],
            "entitlement_issues": [s.summary for s in entitlement_issues],
            "total_signals": len(signals),
            "alerts": sum(1 for s in signals if s.severity.value == "alert"),
            "warnings": sum(1 for s in signals if s.severity.value == "warning"),
        }

    async def check_health(self) -> Dict:
        """Check system health."""
        return {
            "agents_initialized": len(self.agents),
            "active_tasks": len(self.state.active_tasks),
            "completed_tasks": len(self.state.completed_tasks),
            "pending_escalations": len(self.state.pending_escalations),
            "decision_log_entries": len(self.state.decision_log),
        }

    def get_pending_escalations(self) -> List[Dict]:
        """Get pending escalations requiring human approval."""
        return [
            {
                "reason": e.reason.value if hasattr(e.reason, 'value') else str(e.reason),
                "what": e.what,
                "why": e.why,
                "requested_by": e.requested_by.value,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in self.state.pending_escalations
        ]

    async def approve_escalation(self, index: int, approver: str) -> bool:
        """Approve a pending escalation."""
        if 0 <= index < len(self.state.pending_escalations):
            escalation = self.state.pending_escalations[index]
            escalation.approved_by = approver
            escalation.approval_timestamp = datetime.utcnow()

            self._log_decision(
                task_id="ESCALATION",
                agent=AgentRole.TECH_LEAD,
                decision=f"Escalation approved by {approver}",
                rationale=escalation.what,
            )

            self.state.pending_escalations.pop(index)
            return True
        return False
