"""
Product boundary definitions and module ownership mapping.
"""

from typing import Dict, List, Set
from dataclasses import dataclass, field
from pathlib import Path
import re

from ..types import Module, Tier


@dataclass
class ModuleBoundary:
    """Definition of a product module's boundaries."""
    module: Module
    tier: Tier
    description: str
    backend_paths: List[str] = field(default_factory=list)
    frontend_paths: List[str] = field(default_factory=list)
    owned_tables: List[str] = field(default_factory=list)
    owned_routes: List[str] = field(default_factory=list)
    can_import_from: Set[Module] = field(default_factory=set)
    cannot_import_from: Set[Module] = field(default_factory=set)


# Canonical module boundaries
MODULE_BOUNDARIES: Dict[Module, ModuleBoundary] = {
    Module.TRUCK_CORE: ModuleBoundary(
        module=Module.TRUCK_CORE,
        tier=Tier.BASE,
        description="Authentication, org management, truck profiles",
        backend_paths=[
            "app/models/tenant.py",
            "app/api/org_routes.py",
        ],
        frontend_paths=[
            "src/services/orgContext.ts",
            "src/pages/TrucksPage.tsx",
        ],
        owned_tables=["organizations", "trucks"],
        owned_routes=["/api/orgs", "/api/trucks"],
        can_import_from=set(),
        cannot_import_from={
            Module.TRUCK_LEARN,
            Module.TRUCK_CONNECT,
            Module.TRUCK_INSIGHT,
            Module.TRUCK_FLEET,
        },
    ),
    Module.TRUCK_PLAN: ModuleBoundary(
        module=Module.TRUCK_PLAN,
        tier=Tier.BASE,
        description="Plan generation, load sequencing, profit optimization",
        backend_paths=[
            "app/engine/plan_generator.py",
            "app/engine/optimizer.py",
            "app/models/plan.py",
            "app/api/routes.py",
        ],
        frontend_paths=[
            "src/pages/PreflightPage.tsx",
            "src/components/preflight/",
        ],
        owned_tables=["plan_generation_events"],
        owned_routes=["/api/plans/generate", "/api/optimize"],
        can_import_from={Module.TRUCK_CORE},
        cannot_import_from={
            Module.TRUCK_LEARN,
            Module.TRUCK_CONNECT,
            Module.TRUCK_INSIGHT,
            Module.TRUCK_FLEET,
        },
    ),
    Module.TRUCK_TRACK: ModuleBoundary(
        module=Module.TRUCK_TRACK,
        tier=Tier.BASE,
        description="Outcome tracking, predicted vs actual recording",
        backend_paths=[
            "app/models/plan_outcome.py",
            "app/api/outcome_routes.py",
            "app/outcomes/snapshotting.py",
        ],
        frontend_paths=[
            "src/pages/PlanHistoryPage.tsx",
        ],
        owned_tables=[
            "plan_prediction_snapshots",
            "plan_outcomes",
            "decision_events",
        ],
        owned_routes=[
            "/api/outcomes",
            "/api/decisions",
            "/api/plans/history",
        ],
        can_import_from={Module.TRUCK_CORE, Module.TRUCK_PLAN},
        cannot_import_from={
            Module.TRUCK_LEARN,
            Module.TRUCK_CONNECT,
            Module.TRUCK_INSIGHT,
            Module.TRUCK_FLEET,
        },
    ),
    Module.TRUCK_LEARN: ModuleBoundary(
        module=Module.TRUCK_LEARN,
        tier=Tier.PREMIUM,
        description="Calibration engine, trust scoring, bias correction",
        backend_paths=[
            "app/calibration/",
            "app/trust/",
            "app/risk/",
            "app/api/calibration_routes.py",
            "app/api/trust_routes.py",
        ],
        frontend_paths=[],
        owned_tables=[
            "decision_context_snapshots",
        ],
        owned_routes=[
            "/api/calibration/report",
            "/api/trust/report",
            "/api/outcomes/risk_report",
        ],
        can_import_from={
            Module.TRUCK_CORE,
            Module.TRUCK_PLAN,
            Module.TRUCK_TRACK,
        },
        cannot_import_from={
            Module.TRUCK_CONNECT,
            Module.TRUCK_INSIGHT,
            Module.TRUCK_FLEET,
        },
    ),
    Module.TRUCK_CONNECT: ModuleBoundary(
        module=Module.TRUCK_CONNECT,
        tier=Tier.PREMIUM,
        description="Load board integrations, real market data",
        backend_paths=[
            "app/connectors/",
            "app/ingestion/",
        ],
        frontend_paths=[],
        owned_tables=["load_snapshots"],
        owned_routes=["/api/ingestion/status"],
        can_import_from={
            Module.TRUCK_CORE,
            Module.TRUCK_PLAN,
        },
        cannot_import_from={
            Module.TRUCK_LEARN,
            Module.TRUCK_INSIGHT,
            Module.TRUCK_FLEET,
        },
    ),
    Module.TRUCK_INSIGHT: ModuleBoundary(
        module=Module.TRUCK_INSIGHT,
        tier=Tier.PREMIUM,
        description="Analytics, pattern recognition, market intelligence",
        backend_paths=[
            "app/analytics/",
            "app/api/intel_routes.py",
        ],
        frontend_paths=[
            "src/services/intel.ts",
            "src/types/intel.ts",
        ],
        owned_tables=[
            "lane_statistics",
            "market_statistics",
            "destination_scores",
        ],
        owned_routes=[
            "/api/intel/lane",
            "/api/intel/market",
            "/api/intel/destination",
            "/api/intel/negotiation",
        ],
        can_import_from={
            Module.TRUCK_CORE,
            Module.TRUCK_PLAN,
            Module.TRUCK_TRACK,
        },
        cannot_import_from={Module.TRUCK_FLEET},
    ),
    Module.TRUCK_FLEET: ModuleBoundary(
        module=Module.TRUCK_FLEET,
        tier=Tier.ENTERPRISE,
        description="Multi-truck support, fleet-level optimization",
        backend_paths=[],
        frontend_paths=[],
        owned_tables=[],
        owned_routes=[],
        can_import_from={
            Module.TRUCK_CORE,
            Module.TRUCK_PLAN,
            Module.TRUCK_TRACK,
            Module.TRUCK_LEARN,
            Module.TRUCK_CONNECT,
            Module.TRUCK_INSIGHT,
        },
        cannot_import_from=set(),
    ),
}


def get_module_boundaries() -> Dict[Module, ModuleBoundary]:
    """Get all module boundary definitions."""
    return MODULE_BOUNDARIES


def get_module_for_path(file_path: str) -> Module | None:
    """Determine which module owns a given file path."""
    for module, boundary in MODULE_BOUNDARIES.items():
        for pattern in boundary.backend_paths + boundary.frontend_paths:
            if pattern.endswith("/"):
                if pattern.rstrip("/") in file_path:
                    return module
            elif pattern in file_path:
                return module
    return None


def get_module_for_table(table_name: str) -> Module | None:
    """Determine which module owns a given table."""
    for module, boundary in MODULE_BOUNDARIES.items():
        if table_name in boundary.owned_tables:
            return module
    return None


def get_module_for_route(route_path: str) -> Module | None:
    """Determine which module owns a given route."""
    for module, boundary in MODULE_BOUNDARIES.items():
        for pattern in boundary.owned_routes:
            if route_path.startswith(pattern):
                return module
    return None


def check_import_violation(
    from_module: Module,
    to_module: Module,
) -> bool:
    """
    Check if an import from one module to another violates boundaries.

    Returns True if the import is a violation.
    """
    boundary = MODULE_BOUNDARIES.get(from_module)
    if not boundary:
        return False

    return to_module in boundary.cannot_import_from


def detect_import_violations(file_path: Path) -> List[Dict[str, str]]:
    """
    Detect import boundary violations in a Python file.

    Returns list of violations with from_module, to_module, import_line.
    """
    violations = []

    try:
        content = file_path.read_text()
    except FileNotFoundError:
        return violations

    file_module = get_module_for_path(str(file_path))
    if not file_module:
        return violations

    # Get modules this file cannot import from
    boundary = MODULE_BOUNDARIES.get(file_module)
    if not boundary:
        return violations

    # Map module paths for detection
    module_path_map = {
        Module.TRUCK_LEARN: ["calibration", "trust", "risk"],
        Module.TRUCK_CONNECT: ["connectors", "ingestion"],
        Module.TRUCK_INSIGHT: ["analytics", "intel"],
        Module.TRUCK_FLEET: ["fleet"],
    }

    for forbidden_module in boundary.cannot_import_from:
        patterns = module_path_map.get(forbidden_module, [])
        for pattern in patterns:
            # Check for imports
            import_pattern = rf'from\s+app\.{pattern}|import\s+app\.{pattern}'
            matches = re.findall(import_pattern, content)
            for match in matches:
                violations.append({
                    "from_module": file_module.value,
                    "to_module": forbidden_module.value,
                    "import_line": match,
                    "file": str(file_path),
                })

    return violations


def format_boundaries_for_prompt() -> str:
    """Format module boundaries for injection into agent prompts."""
    lines = ["## Product Module Boundaries\n"]

    for tier in [Tier.BASE, Tier.PREMIUM, Tier.ENTERPRISE]:
        tier_modules = [m for m, b in MODULE_BOUNDARIES.items() if b.tier == tier]
        if tier_modules:
            lines.append(f"### {tier.value.title()} Tier\n")

            for module in tier_modules:
                boundary = MODULE_BOUNDARIES[module]
                lines.append(f"**{module.value}**: {boundary.description}")
                if boundary.owned_tables:
                    lines.append(f"- Tables: {', '.join(boundary.owned_tables)}")
                if boundary.owned_routes:
                    lines.append(f"- Routes: {', '.join(boundary.owned_routes[:3])}")
                if boundary.cannot_import_from:
                    forbidden = [m.value for m in boundary.cannot_import_from]
                    lines.append(f"- Cannot import from: {', '.join(forbidden)}")
                lines.append("")

    return "\n".join(lines)
