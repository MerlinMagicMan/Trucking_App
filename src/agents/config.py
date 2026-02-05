"""
Configuration for the multi-agent development team.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, List
from pathlib import Path

from .types import AgentRole, Module, Tier


@dataclass
class AgentConfig:
    """Configuration for an individual agent."""
    role: AgentRole
    can_write_code: bool
    can_veto: bool
    veto_scope: str = ""  # e.g., "feature_placement", "merge_release"
    tools: List[str] = field(default_factory=list)
    prompt_file: str = ""


@dataclass
class TeamConfig:
    """Configuration for the entire development team."""

    # Project paths
    project_root: Path = field(default_factory=lambda: Path("/workspaces/Trucking_App"))
    backend_root: Path = field(default_factory=lambda: Path("/workspaces/Trucking_App/backend"))
    frontend_root: Path = field(default_factory=lambda: Path("/workspaces/Trucking_App/frontend"))
    prompts_dir: Path = field(default_factory=lambda: Path("/workspaces/Trucking_App/src/prompts"))

    # Agent configurations
    agents: Dict[AgentRole, AgentConfig] = field(default_factory=dict)

    # Module tier mappings
    tier_modules: Dict[Tier, Set[Module]] = field(default_factory=dict)

    # Base modules (cannot import from premium)
    base_modules: Set[Module] = field(default_factory=set)
    premium_modules: Set[Module] = field(default_factory=set)

    def __post_init__(self):
        """Initialize default configurations."""
        self._init_agents()
        self._init_tiers()

    def _init_agents(self):
        """Initialize agent configurations."""
        self.agents = {
            AgentRole.TECH_LEAD: AgentConfig(
                role=AgentRole.TECH_LEAD,
                can_write_code=False,
                can_veto=False,
                tools=["task_queue", "message_bus", "decision_log"],
                prompt_file="tech_lead.md",
            ),
            AgentRole.PRODUCT_GUARDIAN: AgentConfig(
                role=AgentRole.PRODUCT_GUARDIAN,
                can_write_code=False,
                can_veto=True,
                veto_scope="feature_placement",
                tools=["decision_log", "escalation_log"],
                prompt_file="product_guardian.md",
            ),
            AgentRole.ARCHITECTURE_OBSERVER: AgentConfig(
                role=AgentRole.ARCHITECTURE_OBSERVER,
                can_write_code=False,
                can_veto=False,
                tools=["file_reader", "schema_analyzer", "import_analyzer"],
                prompt_file="architecture_observer.md",
            ),
            AgentRole.DATABASE_ARCHITECT: AgentConfig(
                role=AgentRole.DATABASE_ARCHITECT,
                can_write_code=True,  # migrations only
                can_veto=False,
                tools=["file_operations", "schema_tools", "alembic_tools"],
                prompt_file="database_architect.md",
            ),
            AgentRole.BACKEND_DEV: AgentConfig(
                role=AgentRole.BACKEND_DEV,
                can_write_code=True,
                can_veto=False,
                tools=["file_operations", "test_runner", "git_tools"],
                prompt_file="backend_dev.md",
            ),
            AgentRole.FRONTEND_DEV: AgentConfig(
                role=AgentRole.FRONTEND_DEV,
                can_write_code=True,
                can_veto=False,
                tools=["file_operations", "test_runner", "git_tools"],
                prompt_file="frontend_dev.md",
            ),
            AgentRole.ALGORITHM_ENGINEER: AgentConfig(
                role=AgentRole.ALGORITHM_ENGINEER,
                can_write_code=True,
                can_veto=False,
                tools=["file_operations", "test_runner", "profiler"],
                prompt_file="algorithm_engineer.md",
            ),
            AgentRole.DEVOPS_ENGINEER: AgentConfig(
                role=AgentRole.DEVOPS_ENGINEER,
                can_write_code=True,  # config only
                can_veto=False,
                tools=["file_operations", "railway_tools", "ci_tools"],
                prompt_file="devops_engineer.md",
            ),
            AgentRole.QA_ENGINEER: AgentConfig(
                role=AgentRole.QA_ENGINEER,
                can_write_code=True,  # tests only
                can_veto=True,
                veto_scope="merge_release",
                tools=["file_operations", "test_runner", "coverage_tools", "security_scanner"],
                prompt_file="qa_engineer.md",
            ),
        }

    def _init_tiers(self):
        """Initialize tier and module mappings."""
        self.tier_modules = {
            Tier.BASE: {
                Module.TRUCK_CORE,
                Module.TRUCK_PLAN,
                Module.TRUCK_TRACK,
            },
            Tier.PREMIUM: {
                Module.TRUCK_CORE,
                Module.TRUCK_PLAN,
                Module.TRUCK_TRACK,
                Module.TRUCK_LEARN,
                Module.TRUCK_CONNECT,
                Module.TRUCK_INSIGHT,
            },
            Tier.ENTERPRISE: {
                Module.TRUCK_CORE,
                Module.TRUCK_PLAN,
                Module.TRUCK_TRACK,
                Module.TRUCK_LEARN,
                Module.TRUCK_CONNECT,
                Module.TRUCK_INSIGHT,
                Module.TRUCK_FLEET,
            },
        }

        self.base_modules = {
            Module.TRUCK_CORE,
            Module.TRUCK_PLAN,
            Module.TRUCK_TRACK,
        }

        self.premium_modules = {
            Module.TRUCK_LEARN,
            Module.TRUCK_CONNECT,
            Module.TRUCK_INSIGHT,
            Module.TRUCK_FLEET,
        }


# Singleton configuration
_config: TeamConfig | None = None


def get_config() -> TeamConfig:
    """Get the team configuration singleton."""
    global _config
    if _config is None:
        _config = TeamConfig()
    return _config


def reset_config():
    """Reset configuration (for testing)."""
    global _config
    _config = None
