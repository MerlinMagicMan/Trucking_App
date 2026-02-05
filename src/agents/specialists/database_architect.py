"""
Database Architect Agent - Owns schema and migrations.
"""

from typing import Dict, Any, List
from pathlib import Path
import re

from ..types import (
    AgentRole, Task, Message, Module, SchemaProposal,
)
from ..context.schema import extract_sqlalchemy_models, ModelInfo
from .base import ImplementerAgent, AgentResponse


class DatabaseArchitectAgent(ImplementerAgent):
    """
    Database Architect owns SQLAlchemy models and Alembic migrations.

    ONLY agent that can name new tables/columns.
    Guardian of the Schema Constitution.
    """

    def __init__(self):
        super().__init__(AgentRole.DATABASE_ARCHITECT)
        self.backend_root = Path("/workspaces/Trucking_App/backend")

    async def propose_schema_change(
        self,
        description: str,
        module: Module,
    ) -> SchemaProposal:
        """
        Propose a schema change.

        This is the ONLY way new tables/columns can be named.
        """
        self.log(f"Proposing schema change: {description}")

        # Analyze the request
        new_tables = self._identify_new_tables(description)
        new_columns = self._identify_new_columns(description)
        affected_tables = self._identify_affected_tables(description)

        # Check migration safety
        safe, safety_concerns = self._check_migration_safety(new_tables, new_columns)

        # Generate rollback plan
        rollback = self._generate_rollback_plan(new_tables, new_columns)

        return SchemaProposal(
            description=description,
            tables_affected=affected_tables,
            new_tables=new_tables,
            new_columns=new_columns,
            migration_safe=safe,
            rollback_plan=rollback,
            module=module,
            data_migration_needed=self._needs_data_migration(description),
        )

    def _identify_new_tables(self, description: str) -> List[str]:
        """Identify new tables needed."""
        tables = []
        desc_lower = description.lower()

        # Pattern matching for common table requests
        if "user preference" in desc_lower:
            tables.append("user_preferences")
        if "notification" in desc_lower:
            tables.append("notifications")
        if "audit" in desc_lower and "log" in desc_lower:
            tables.append("audit_logs")

        return tables

    def _identify_new_columns(self, description: str) -> Dict[str, List[str]]:
        """Identify new columns needed, mapped to tables."""
        columns: Dict[str, List[str]] = {}

        # This would be more sophisticated in production
        # For now, return empty - actual columns determined during implementation

        return columns

    def _identify_affected_tables(self, description: str) -> List[str]:
        """Identify tables that will be affected."""
        affected = []
        desc_lower = description.lower()

        # Map keywords to tables
        table_keywords = {
            "plan": ["plan_generation_events", "plan_prediction_snapshots"],
            "outcome": ["plan_outcomes"],
            "decision": ["decision_events", "decision_context_snapshots"],
            "calibration": ["decision_context_snapshots"],
            "trust": ["decision_context_snapshots"],
            "truck": ["trucks"],
            "org": ["organizations"],
        }

        for keyword, tables in table_keywords.items():
            if keyword in desc_lower:
                affected.extend(tables)

        return list(set(affected))

    def _check_migration_safety(
        self,
        new_tables: List[str],
        new_columns: Dict[str, List[str]],
    ) -> tuple[bool, List[str]]:
        """Check if migration is safe to run."""
        concerns = []

        # New tables are always safe
        # Adding nullable columns is safe
        # Adding NOT NULL columns is not safe without default

        for table, cols in new_columns.items():
            for col in cols:
                if "not null" in col.lower() and "default" not in col.lower():
                    concerns.append(f"Column {col} on {table} is NOT NULL without default")

        return len(concerns) == 0, concerns

    def _generate_rollback_plan(
        self,
        new_tables: List[str],
        new_columns: Dict[str, List[str]],
    ) -> str:
        """Generate rollback plan for the migration."""
        steps = []

        for table in new_tables:
            steps.append(f"DROP TABLE IF EXISTS {table};")

        for table, cols in new_columns.items():
            for col in cols:
                col_name = col.split()[0] if col else "unknown"
                steps.append(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col_name};")

        return "\n".join(steps) if steps else "No rollback needed"

    def _needs_data_migration(self, description: str) -> bool:
        """Check if data migration is needed."""
        desc_lower = description.lower()
        return any(word in desc_lower for word in [
            "migrate data", "backfill", "populate", "copy from",
        ])

    async def validate_schema_constitution(self) -> List[Dict[str, Any]]:
        """
        Validate current schema against constitution rules.

        Returns list of violations.
        """
        violations = []
        models = extract_sqlalchemy_models(self.backend_root)

        for name, model in models.items():
            # Rule 1: All monetary columns use Numeric
            for col in model.columns:
                if any(word in col.name.lower() for word in ["cost", "revenue", "profit", "rate", "price"]):
                    if col.type.lower() not in ["numeric", "decimal"]:
                        violations.append({
                            "rule": "RULE-001",
                            "model": name,
                            "column": col.name,
                            "issue": f"Monetary column uses {col.type}, should be Numeric",
                        })

            # Rule 2: All business tables have org_id
            if name not in ["Organization", "Base"]:
                has_org_id = any(col.name == "org_id" for col in model.columns)
                if not has_org_id and "org" not in name.lower():
                    violations.append({
                        "rule": "RULE-002",
                        "model": name,
                        "issue": "Business table missing org_id column",
                    })

            # Rule 3: All tables have timestamps
            has_created = any(col.name == "created_at" for col in model.columns)
            has_updated = any(col.name == "updated_at" for col in model.columns)
            if not has_created or not has_updated:
                violations.append({
                    "rule": "RULE-003",
                    "model": name,
                    "issue": f"Missing timestamp columns (created_at: {has_created}, updated_at: {has_updated})",
                })

        return violations

    async def implement(self, task: Task) -> AgentResponse:
        """Implement a schema change task."""
        self.log(f"Implementing schema change: {task.description}")

        # Generate proposal
        proposal = await self.propose_schema_change(
            task.description,
            task.module or Module.TRUCK_CORE,
        )

        if not proposal.migration_safe:
            return AgentResponse(
                success=False,
                message="Migration is not safe - review required",
                data={"proposal": proposal.__dict__},
            )

        # Generate Alembic migration template
        migration_code = self._generate_migration_template(proposal)

        return AgentResponse(
            success=True,
            message="Schema proposal ready for review",
            data={
                "proposal": {
                    "description": proposal.description,
                    "new_tables": proposal.new_tables,
                    "new_columns": proposal.new_columns,
                    "migration_safe": proposal.migration_safe,
                    "rollback_plan": proposal.rollback_plan,
                },
                "migration_template": migration_code,
            },
        )

    def _generate_migration_template(self, proposal: SchemaProposal) -> str:
        """Generate Alembic migration template."""
        return f'''"""
{proposal.description}

Revision ID: [generated]
Revises: [previous]
Create Date: [timestamp]

Migration: {proposal.description}
- Safe to run: {"Yes" if proposal.migration_safe else "No - review required"}
- Rollback: {proposal.rollback_plan}
- Module: {proposal.module.value}
- Data migration needed: {"Yes" if proposal.data_migration_needed else "No"}
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "[generated]"
down_revision = "[previous]"
branch_labels = None
depends_on = None


def upgrade():
    # TODO: Implement upgrade
    pass


def downgrade():
    # TODO: Implement downgrade
    {proposal.rollback_plan}
'''

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages requesting schema work."""
        self.log(f"Schema request from {message.from_agent.value}: {message.subject}")

        if "validate" in message.subject.lower():
            violations = await self.validate_schema_constitution()
            return AgentResponse(
                success=len(violations) == 0,
                message=f"Found {len(violations)} constitution violations",
                data={"violations": violations},
            )

        # Default: create proposal
        proposal = await self.propose_schema_change(
            message.content,
            Module.TRUCK_CORE,  # Default, should be parsed
        )

        return AgentResponse(
            success=True,
            message="Schema proposal created",
            data={"proposal": proposal.__dict__},
        )
