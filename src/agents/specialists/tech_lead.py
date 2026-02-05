"""
Tech Lead Agent - Orchestrator for the development team.
"""

from typing import Dict, Any, List
import uuid

from ..types import (
    AgentRole, Task, TaskBreakdown, TaskType, TaskStatus,
    Module, Tier, Message, EscalationReason,
)
from ..context import (
    get_schema_summary,
    get_routes_summary,
    get_frontend_summary,
)
from ..context.product_boundaries import format_boundaries_for_prompt
from .base import BaseAgent, AgentResponse


class TechLeadAgent(BaseAgent):
    """
    Tech Lead orchestrates the development team.

    Responsibilities:
    - Task breakdown and assignment
    - Conflict resolution
    - Escalation management
    - Final technical authority (except for vetoes)
    """

    def __init__(self):
        super().__init__(AgentRole.TECH_LEAD)

    def get_context(self) -> Dict[str, str]:
        """Get current codebase context for prompt injection."""
        return {
            "SCHEMA_CONTEXT": get_schema_summary(),
            "ROUTES_CONTEXT": get_routes_summary(),
            "FRONTEND_CONTEXT": get_frontend_summary(),
            "MODULE_BOUNDARIES": format_boundaries_for_prompt(),
            "SCHEMA_CONSTITUTION": "See Schema Constitution document",
        }

    async def break_down_task(self, description: str) -> TaskBreakdown:
        """
        Break down a user request into tasks for specialists.

        This is the main entry point for new work.
        """
        self.log(f"Breaking down task: {description}")

        # Analyze the request to determine type and module
        task_type = self._classify_task_type(description)
        module = self._identify_module(description)
        tier = self._get_tier_for_module(module)

        # Check for schema changes
        schema_changes = self._requires_schema_changes(description)

        # Check for algorithm changes
        algorithm_changes = self._requires_algorithm_changes(description)

        # Generate tasks
        tasks = self._generate_tasks(description, task_type, module, schema_changes, algorithm_changes)

        # Check for escalation requirements
        escalation_required, escalation_reason = self._check_escalation(description, algorithm_changes)

        return TaskBreakdown(
            summary=description,
            type=task_type,
            module=module,
            tier=tier,
            guardian_approved=False,  # Will be set after guardian review
            schema_changes_required=schema_changes,
            algorithm_changes_required=algorithm_changes,
            import_boundary_verified=False,  # Will be verified
            tasks=tasks,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
        )

    def _classify_task_type(self, description: str) -> TaskType:
        """Classify the type of task."""
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["bug", "fix", "broken", "error"]):
            return TaskType.BUGFIX
        elif any(word in desc_lower for word in ["refactor", "clean", "reorganize"]):
            return TaskType.REFACTOR
        elif any(word in desc_lower for word in ["deploy", "ci", "pipeline", "railway"]):
            return TaskType.INFRASTRUCTURE
        elif any(word in desc_lower for word in ["review", "audit", "check"]):
            return TaskType.AUDIT
        else:
            return TaskType.FEATURE

    def _identify_module(self, description: str) -> Module:
        """Identify which module the task belongs to."""
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["calibrat", "trust", "learn"]):
            return Module.TRUCK_LEARN
        elif any(word in desc_lower for word in ["load board", "dat", "truckstop", "connect"]):
            return Module.TRUCK_CONNECT
        elif any(word in desc_lower for word in ["analytic", "intel", "insight"]):
            return Module.TRUCK_INSIGHT
        elif any(word in desc_lower for word in ["fleet", "multi-truck"]):
            return Module.TRUCK_FLEET
        elif any(word in desc_lower for word in ["outcome", "track", "actual"]):
            return Module.TRUCK_TRACK
        elif any(word in desc_lower for word in ["plan", "optim", "generat"]):
            return Module.TRUCK_PLAN
        else:
            return Module.TRUCK_CORE

    def _get_tier_for_module(self, module: Module) -> Tier:
        """Get the tier for a module."""
        if module in {Module.TRUCK_CORE, Module.TRUCK_PLAN, Module.TRUCK_TRACK}:
            return Tier.BASE
        elif module == Module.TRUCK_FLEET:
            return Tier.ENTERPRISE
        else:
            return Tier.PREMIUM

    def _requires_schema_changes(self, description: str) -> bool:
        """Check if the task requires schema changes."""
        desc_lower = description.lower()
        return any(word in desc_lower for word in [
            "new table", "add column", "migration", "schema",
            "database", "model", "field",
        ])

    def _requires_algorithm_changes(self, description: str) -> bool:
        """Check if the task requires algorithm changes."""
        desc_lower = description.lower()
        return any(word in desc_lower for word in [
            "algorithm", "optim", "calibrat", "trust score",
            "formula", "calculation", "weight",
        ])

    def _generate_tasks(
        self,
        description: str,
        task_type: TaskType,
        module: Module,
        schema_changes: bool,
        algorithm_changes: bool,
    ) -> List[Task]:
        """Generate tasks for the breakdown."""
        tasks = []

        # Always start with product guardian review for features
        if task_type == TaskType.FEATURE:
            tasks.append(Task(
                id=f"TASK-{uuid.uuid4().hex[:8]}",
                description="Product Boundary Guardian review",
                type=TaskType.REVIEW,
                assigned_to=AgentRole.PRODUCT_GUARDIAN,
                module=module,
            ))

        # Schema changes first
        if schema_changes:
            tasks.append(Task(
                id=f"TASK-{uuid.uuid4().hex[:8]}",
                description="Database schema proposal and migration",
                type=task_type,
                assigned_to=AgentRole.DATABASE_ARCHITECT,
                module=module,
                dependencies=[t.id for t in tasks],
            ))

        # Algorithm changes need Algorithm Engineer
        if algorithm_changes:
            tasks.append(Task(
                id=f"TASK-{uuid.uuid4().hex[:8]}",
                description="Algorithm design with test vectors",
                type=task_type,
                assigned_to=AgentRole.ALGORITHM_ENGINEER,
                module=module,
                dependencies=[t.id for t in tasks],
            ))

        # Backend implementation
        tasks.append(Task(
            id=f"TASK-{uuid.uuid4().hex[:8]}",
            description=f"Backend implementation: {description}",
            type=task_type,
            assigned_to=AgentRole.BACKEND_DEV,
            module=module,
            dependencies=[t.id for t in tasks],
        ))

        # Frontend if needed
        if self._needs_frontend(description):
            tasks.append(Task(
                id=f"TASK-{uuid.uuid4().hex[:8]}",
                description=f"Frontend implementation: {description}",
                type=task_type,
                assigned_to=AgentRole.FRONTEND_DEV,
                module=module,
                dependencies=[t.id for t in tasks if t.assigned_to == AgentRole.BACKEND_DEV],
            ))

        # QA review at the end
        tasks.append(Task(
            id=f"TASK-{uuid.uuid4().hex[:8]}",
            description="Code review and test coverage",
            type=TaskType.REVIEW,
            assigned_to=AgentRole.QA_ENGINEER,
            module=module,
            dependencies=[t.id for t in tasks if t.assigned_to in {
                AgentRole.BACKEND_DEV, AgentRole.FRONTEND_DEV
            }],
        ))

        return tasks

    def _needs_frontend(self, description: str) -> bool:
        """Check if the task needs frontend work."""
        desc_lower = description.lower()
        return any(word in desc_lower for word in [
            "ui", "page", "component", "button", "display",
            "show", "view", "dashboard", "tab",
        ])

    def _check_escalation(
        self,
        description: str,
        algorithm_changes: bool,
    ) -> tuple[bool, EscalationReason | None]:
        """Check if the task requires human escalation."""
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["dat", "truckstop", "load board integration"]):
            return True, EscalationReason.EXTERNAL_INTEGRATION

        if any(word in desc_lower for word in ["hos", "hours of service"]):
            return True, EscalationReason.HOS_MODEL_CHANGE

        if algorithm_changes and any(word in desc_lower for word in ["trust", "calibrat"]):
            return True, EscalationReason.ALGORITHM_TRUST_IMPLICATIONS

        return False, None

    async def process_task(self, task: Task) -> AgentResponse:
        """Tech Lead doesn't process individual tasks, it orchestrates."""
        return AgentResponse(
            success=False,
            message="Tech Lead orchestrates, doesn't implement. Use break_down_task() instead.",
        )

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages from other agents."""
        self.log(f"Received message from {message.from_agent.value}: {message.subject}")

        # Handle different message types
        if "veto" in message.subject.lower():
            return await self._handle_veto(message)
        elif "escalat" in message.subject.lower():
            return await self._handle_escalation(message)
        elif "conflict" in message.subject.lower():
            return await self._handle_conflict(message)
        else:
            return AgentResponse(
                success=True,
                message="Message acknowledged",
            )

    async def _handle_veto(self, message: Message) -> AgentResponse:
        """Handle a veto from Product Guardian or QA."""
        self.log(f"Veto received: {message.content}")

        return AgentResponse(
            success=True,
            message="Veto acknowledged. Escalating to human.",
            requires_escalation=True,
            escalation_reason="Agent veto requires human override",
        )

    async def _handle_escalation(self, message: Message) -> AgentResponse:
        """Handle an escalation request."""
        self.log(f"Escalation requested: {message.content}")

        return AgentResponse(
            success=True,
            message="Escalation logged. Awaiting human approval.",
            requires_escalation=True,
            escalation_reason=message.content,
        )

    async def _handle_conflict(self, message: Message) -> AgentResponse:
        """Handle a conflict between agents."""
        self.log(f"Conflict resolution needed: {message.content}")

        # Apply conflict resolution priorities
        # 1. Algorithm correctness
        # 2. Data integrity
        # 3. Org isolation
        # 4. Monetization protection
        # 5. User experience
        # 6. Development velocity

        return AgentResponse(
            success=True,
            message="Conflict resolution applied based on priority rules",
            data={"resolution_priority": "See tech_lead.md conflict resolution protocol"},
        )
