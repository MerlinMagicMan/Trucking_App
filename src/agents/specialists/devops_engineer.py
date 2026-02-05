"""
DevOps Engineer Agent - Owns deployment and infrastructure.
"""

from typing import Dict, Any, List
from pathlib import Path

from ..types import AgentRole, Task, Message
from ..context.infrastructure import (
    extract_railway_config,
    extract_github_workflows,
    extract_env_template,
)
from .base import ImplementerAgent, AgentResponse


class DevOpsEngineerAgent(ImplementerAgent):
    """
    DevOps Engineer owns Railway deployment, CI/CD, and infrastructure.

    Can write:
    - Configuration files
    - CI/CD workflows
    - Deployment scripts
    """

    def __init__(self):
        super().__init__(AgentRole.DEVOPS_ENGINEER)
        self.project_root = Path("/workspaces/Trucking_App")

    async def implement(self, task: Task) -> AgentResponse:
        """Implement an infrastructure task."""
        self.log(f"Implementing: {task.description}")

        # Analyze current infrastructure
        current_state = await self._analyze_infrastructure()

        # Plan changes
        plan = self._plan_changes(task, current_state)

        return AgentResponse(
            success=True,
            message="Infrastructure plan ready",
            data={
                "current_state": current_state,
                "planned_changes": plan,
            },
        )

    async def _analyze_infrastructure(self) -> Dict[str, Any]:
        """Analyze current infrastructure state."""
        railway = extract_railway_config(self.project_root)
        workflows = extract_github_workflows(self.project_root)
        env_vars = extract_env_template(self.project_root)

        return {
            "railway": {
                "configured": railway is not None,
                "build_command": railway.build_command if railway else None,
                "start_command": railway.start_command if railway else None,
            },
            "github_actions": {
                "workflow_count": len(workflows),
                "workflows": [w.name for w in workflows],
            },
            "env_vars": env_vars,
        }

    def _plan_changes(self, task: Task, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Plan infrastructure changes."""
        desc_lower = task.description.lower()
        plan: Dict[str, Any] = {
            "files_to_create": [],
            "files_to_modify": [],
            "env_vars_to_add": [],
            "services_to_configure": [],
        }

        if "ci" in desc_lower or "pipeline" in desc_lower:
            plan["files_to_create"].append(".github/workflows/ci.yml")

        if "railway" in desc_lower or "deploy" in desc_lower:
            if not current_state["railway"]["configured"]:
                plan["files_to_create"].append("railway.toml")
            else:
                plan["files_to_modify"].append("railway.toml")

        if "secret" in desc_lower or "env" in desc_lower:
            plan["env_vars_to_add"].append("NEW_ENV_VAR")

        return plan

    def generate_railway_config(
        self,
        build_command: str = "cd backend && pip install -r requirements.txt",
        start_command: str = "cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
        health_check: str = "/api/health",
    ) -> str:
        """Generate Railway configuration."""
        return f'''[build]
builder = "nixpacks"
buildCommand = "{build_command}"

[deploy]
startCommand = "{start_command}"
healthcheckPath = "{health_check}"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
'''

    def generate_github_workflow(
        self,
        name: str = "CI",
        python_version: str = "3.11",
        node_version: str = "18",
    ) -> str:
        """Generate GitHub Actions workflow."""
        return f'''name: {name}

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "{node_version}"

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Type check
        run: |
          cd frontend
          npm run build

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"

      - name: Install linters
        run: pip install ruff mypy

      - name: Run ruff
        run: ruff check backend/

      - name: Run mypy
        run: mypy backend/app --ignore-missing-imports
'''

    def generate_env_template(self, modules: List[str] | None = None) -> str:
        """Generate .env.example template."""
        base_vars = '''# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/trucking

# Auth
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256

# App
APP_ENV=development
LOG_LEVEL=INFO
'''

        premium_vars = '''
# Premium Module Flags
ENABLE_TRUCK_LEARN=false
ENABLE_TRUCK_CONNECT=false
ENABLE_TRUCK_INSIGHT=false
ENABLE_TRUCK_FLEET=false
'''

        integration_vars = '''
# Load Board Integrations (Premium)
DAT_API_KEY=
TRUCKSTOP_API_KEY=
'''

        monitoring_vars = '''
# Monitoring
SENTRY_DSN=
'''

        return base_vars + premium_vars + integration_vars + monitoring_vars

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages from other agents."""
        self.log(f"Message from {message.from_agent.value}: {message.subject}")

        if "railway" in message.subject.lower():
            config = self.generate_railway_config()
            return AgentResponse(
                success=True,
                message="Railway config generated",
                data={"config": config},
            )

        if "workflow" in message.subject.lower() or "ci" in message.subject.lower():
            workflow = self.generate_github_workflow()
            return AgentResponse(
                success=True,
                message="GitHub workflow generated",
                data={"workflow": workflow},
            )

        return AgentResponse(
            success=True,
            message="Message acknowledged",
        )
