"""
Backend Developer Agent - Owns FastAPI endpoints and business logic.
"""

from typing import Dict, Any, List
from pathlib import Path

from ..types import AgentRole, Task, Message, Module
from ..context.routes import extract_fastapi_routes
from ..context.product_boundaries import MODULE_BOUNDARIES
from .base import ImplementerAgent, AgentResponse


class BackendDevAgent(ImplementerAgent):
    """
    Backend Developer owns FastAPI endpoints and business logic.

    Must follow:
    - Schema integrity (no inventing tables/columns)
    - Decimal-only money
    - Org scoping
    - Import boundaries
    - Entitlement enforcement
    """

    def __init__(self):
        super().__init__(AgentRole.BACKEND_DEV)
        self.backend_root = Path("/workspaces/Trucking_App/backend")

    async def implement(self, task: Task) -> AgentResponse:
        """Implement a backend task."""
        self.log(f"Implementing: {task.description}")

        # Check preconditions
        checks = await self._run_prechecks(task)
        if not checks["passed"]:
            return AgentResponse(
                success=False,
                message=f"Prechecks failed: {checks['failures']}",
                data=checks,
            )

        # Determine implementation approach
        approach = self._plan_implementation(task)

        return AgentResponse(
            success=True,
            message="Implementation plan ready",
            data={
                "task_id": task.id,
                "approach": approach,
                "files_to_create": approach.get("new_files", []),
                "files_to_modify": approach.get("modify_files", []),
                "tests_required": approach.get("tests", []),
            },
        )

    async def _run_prechecks(self, task: Task) -> Dict[str, Any]:
        """Run prechecks before implementation."""
        failures = []

        # Check 1: Module boundaries
        if task.module:
            boundary = MODULE_BOUNDARIES.get(task.module)
            if boundary and boundary.tier.value != "base":
                # Premium module - need to verify entitlement pattern will be used
                pass  # Will be enforced in code review

        # Check 2: Schema exists for referenced tables
        # (Would check against actual schema here)

        return {
            "passed": len(failures) == 0,
            "failures": failures,
        }

    def _plan_implementation(self, task: Task) -> Dict[str, Any]:
        """Plan the implementation approach."""
        desc_lower = task.description.lower()
        plan: Dict[str, Any] = {
            "new_files": [],
            "modify_files": [],
            "tests": [],
            "patterns": [],
        }

        # Determine what's needed based on description
        if "endpoint" in desc_lower or "api" in desc_lower:
            plan["patterns"].append("fastapi_endpoint")
            if task.module:
                route_file = f"app/api/{task.module.value.lower()}_routes.py"
                plan["modify_files"].append(route_file)

        if "service" in desc_lower or "business logic" in desc_lower:
            plan["patterns"].append("service_layer")

        if task.module and task.module.value.startswith("TRUCK_"):
            # Add entitlement check pattern for premium
            tier = MODULE_BOUNDARIES.get(task.module)
            if tier and tier.tier.value != "base":
                plan["patterns"].append("entitlement_enforcement")

        # Always need tests
        plan["tests"].append(f"test_{task.id.lower()}.py")

        return plan

    def generate_endpoint_template(
        self,
        method: str,
        path: str,
        function_name: str,
        module: Module,
        requires_entitlement: bool = False,
    ) -> str:
        """Generate a FastAPI endpoint template."""
        entitlement_check = ""
        if requires_entitlement:
            entitlement_check = f'''
    # Entitlement check (AUTHORITATIVE)
    await require_entitlement(org_id, Module.{module.value})
'''

        return f'''
@router.{method.lower()}("{path}")
async def {function_name}(
    org_id: str = Header(..., alias="X-Org-Id"),
    db: Session = Depends(get_db),
):
    """
    {function_name.replace("_", " ").title()}

    Module: {module.value}
    """
    # Validate org access
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
{entitlement_check}
    # TODO: Implement business logic

    return {{"status": "ok"}}
'''

    def generate_service_template(
        self,
        service_name: str,
        module: Module,
    ) -> str:
        """Generate a service class template."""
        return f'''"""
{service_name} service for {module.value}.
"""

from decimal import Decimal
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.tenant import Organization


class {service_name}:
    """
    {service_name} handles business logic for {module.value}.

    All monetary values use Decimal.
    All queries are org-scoped.
    """

    def __init__(self, db: Session, org_id: str):
        self.db = db
        self.org_id = org_id

    def _validate_org(self) -> Organization:
        """Validate org exists and return it."""
        org = self.db.query(Organization).filter(
            Organization.id == self.org_id
        ).first()
        if not org:
            raise ValueError(f"Organization {{self.org_id}} not found")
        return org

    # TODO: Add service methods
'''

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages from other agents."""
        self.log(f"Message from {message.from_agent.value}: {message.subject}")

        if "template" in message.subject.lower():
            # Generate template based on request
            if "endpoint" in message.content.lower():
                template = self.generate_endpoint_template(
                    method="GET",
                    path="/api/example",
                    function_name="example_endpoint",
                    module=Module.TRUCK_CORE,
                )
                return AgentResponse(
                    success=True,
                    message="Endpoint template generated",
                    data={"template": template},
                )

        return AgentResponse(
            success=True,
            message="Message acknowledged",
        )
