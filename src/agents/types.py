"""
Core type definitions for the multi-agent development team.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from datetime import datetime


class AgentRole(str, Enum):
    """Roles in the development team."""
    TECH_LEAD = "tech_lead"
    PRODUCT_GUARDIAN = "product_guardian"
    ARCHITECTURE_OBSERVER = "architecture_observer"
    DATABASE_ARCHITECT = "database_architect"
    BACKEND_DEV = "backend_dev"
    FRONTEND_DEV = "frontend_dev"
    ALGORITHM_ENGINEER = "algorithm_engineer"
    DEVOPS_ENGINEER = "devops_engineer"
    QA_ENGINEER = "qa_engineer"


class TaskType(str, Enum):
    """Types of development tasks."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    INFRASTRUCTURE = "infrastructure"
    REVIEW = "review"
    AUDIT = "audit"


class TaskStatus(str, Enum):
    """Status of a task in the pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    COMPLETED = "completed"
    VETOED = "vetoed"
    ESCALATED = "escalated"


class Tier(str, Enum):
    """Product tiers for entitlements."""
    BASE = "base"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class Module(str, Enum):
    """Product modules."""
    TRUCK_CORE = "TRUCK_CORE"
    TRUCK_PLAN = "TRUCK_PLAN"
    TRUCK_TRACK = "TRUCK_TRACK"
    TRUCK_LEARN = "TRUCK_LEARN"
    TRUCK_CONNECT = "TRUCK_CONNECT"
    TRUCK_INSIGHT = "TRUCK_INSIGHT"
    TRUCK_FLEET = "TRUCK_FLEET"


class VetoType(str, Enum):
    """Types of vetoes that can be issued."""
    PRODUCT_BOUNDARY = "product_boundary"
    QUALITY_GATE = "quality_gate"
    SCHEMA_VIOLATION = "schema_violation"
    IMPORT_BOUNDARY = "import_boundary"


class EscalationReason(str, Enum):
    """Reasons for escalating to human."""
    PRODUCT_GUARDIAN_VETO_OVERRIDE = "product_guardian_veto_override"
    SCHEMA_CONSTITUTION_VIOLATION = "schema_constitution_violation"
    ALGORITHM_TRUST_IMPLICATIONS = "algorithm_change_with_trust_implications"
    EXTERNAL_INTEGRATION = "integration_with_external_load_boards"
    HOS_MODEL_CHANGE = "hos_model_changes"
    NONDETERMINISTIC_ALGORITHM = "nondeterministic_algorithm_approval"


class SignalSeverity(str, Enum):
    """Severity levels for architecture signals."""
    INFO = "info"
    WARNING = "warning"
    CONCERN = "concern"
    ALERT = "alert"


@dataclass
class Task:
    """A development task."""
    id: str
    description: str
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[AgentRole] = None
    module: Optional[Module] = None
    tier: Optional[Tier] = None
    dependencies: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskBreakdown:
    """Result of Tech Lead breaking down a request."""
    summary: str
    type: TaskType
    module: Module
    tier: Tier
    guardian_approved: bool
    schema_changes_required: bool
    algorithm_changes_required: bool
    import_boundary_verified: bool
    tasks: List[Task]
    escalation_required: bool = False
    escalation_reason: Optional[EscalationReason] = None


@dataclass
class ProductBoundaryReview:
    """Result of Product Guardian reviewing a feature."""
    feature: str
    proposed_location: str
    belongs_to: Module
    tier: Tier
    rationale: str
    base_to_premium_imports: bool
    adapter_pattern_required: bool
    value_leakage_risk: str  # none, low, medium, high, critical
    base_tier_alternative: Optional[str]
    upgrade_driver: Optional[str]
    decision: str  # APPROVE, RELOCATE, VETO
    veto_reason: Optional[str] = None
    value_leaked: Optional[str] = None
    alternative: Optional[str] = None


@dataclass
class ArchitectureSignal:
    """A signal from the Architecture Observer."""
    observation_type: str
    severity: SignalSeverity
    summary: str
    evidence: List[str]
    recommendation: str
    priority: str  # when_convenient, next_sprint, soon, urgent
    owner: AgentRole


@dataclass
class CodeReviewResult:
    """Result of QA Engineer code review."""
    file_path: str
    blocking_issues: List[Dict[str, Any]]
    major_issues: List[Dict[str, Any]]
    minor_issues: List[Dict[str, Any]]
    merge_decision: str  # APPROVE, BLOCKED
    block_reasons: List[str]


@dataclass
class SchemaProposal:
    """A proposed schema change from Database Architect."""
    description: str
    tables_affected: List[str]
    new_tables: List[str]
    new_columns: Dict[str, List[str]]  # table -> columns
    migration_safe: bool
    rollback_plan: str
    module: Module
    data_migration_needed: bool
    alembic_revision: Optional[str] = None


@dataclass
class AlgorithmProposal:
    """A proposed algorithm change from Algorithm Engineer."""
    name: str
    module: Module
    tier: Tier
    purpose: str
    deterministic: bool
    nondeterminism_reason: Optional[str]
    inputs: Dict[str, str]  # param -> description
    outputs: Dict[str, str]  # return -> description
    complexity_time: str
    complexity_space: str
    search_space: str
    pruning_strategy: str
    test_vectors: List[Dict[str, Any]]
    decimal_fields: List[str]
    requires_escalation: bool = False


@dataclass
class EscalationRequest:
    """A request for human escalation."""
    reason: EscalationReason
    what: str
    why: str
    risk: str
    mitigation: str
    requested_by: AgentRole
    timestamp: datetime = field(default_factory=datetime.utcnow)
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None


@dataclass
class DecisionLogEntry:
    """A logged decision for audit trail."""
    decision_id: str
    task_id: str
    agent: AgentRole
    decision: str
    rationale: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    alternatives_considered: List[str] = field(default_factory=list)
    risks_acknowledged: List[str] = field(default_factory=list)


@dataclass
class Message:
    """A message between agents."""
    id: str
    from_agent: AgentRole
    to_agent: AgentRole
    subject: str
    content: str
    priority: str  # low, normal, high, urgent
    timestamp: datetime = field(default_factory=datetime.utcnow)
    requires_response: bool = False
    in_reply_to: Optional[str] = None
