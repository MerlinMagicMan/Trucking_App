"""
Architecture Observer Agent - Monitors systemic health.
"""

from typing import Dict, Any, List
from pathlib import Path

from ..types import (
    AgentRole, Task, Message, ArchitectureSignal, SignalSeverity,
)
from ..context.product_boundaries import detect_import_violations
from .base import ReviewerAgent, AgentResponse


class ArchitectureObserverAgent(ReviewerAgent):
    """
    Architecture Observer monitors systemic health.

    Advisory only - never blocks, never writes code.
    """

    def __init__(self):
        super().__init__(AgentRole.ARCHITECTURE_OBSERVER)

    async def scan_codebase(self) -> List[ArchitectureSignal]:
        """
        Scan the codebase for architectural issues.

        Returns a list of signals about systemic health.
        """
        self.log("Scanning codebase for architectural issues")
        signals = []

        # Check import boundaries
        signals.extend(await self._check_import_boundaries())

        # Check decimal usage
        signals.extend(await self._check_decimal_usage())

        # Check org scoping
        signals.extend(await self._check_org_scoping())

        # Check determinism
        signals.extend(await self._check_determinism())

        # Check entitlement coverage
        signals.extend(await self._check_entitlement_coverage())

        return signals

    async def _check_import_boundaries(self) -> List[ArchitectureSignal]:
        """Check for import boundary violations."""
        signals = []
        backend_root = Path("/workspaces/Trucking_App/backend")

        # Scan base module files
        base_paths = [
            backend_root / "app" / "engine",
            backend_root / "app" / "models" / "tenant.py",
            backend_root / "app" / "models" / "plan.py",
        ]

        for path in base_paths:
            if path.is_dir():
                for py_file in path.glob("*.py"):
                    violations = detect_import_violations(py_file)
                    for v in violations:
                        signals.append(ArchitectureSignal(
                            observation_type="import_violation",
                            severity=SignalSeverity.ALERT,
                            summary=f"Base module imports from premium: {v['from_module']} → {v['to_module']}",
                            evidence=[f"File: {v['file']}", f"Import: {v['import_line']}"],
                            recommendation="Remove direct import; use adapter pattern if needed",
                            priority="urgent",
                            owner=AgentRole.BACKEND_DEV,
                        ))
            elif path.is_file():
                violations = detect_import_violations(path)
                for v in violations:
                    signals.append(ArchitectureSignal(
                        observation_type="import_violation",
                        severity=SignalSeverity.ALERT,
                        summary=f"Import boundary violation in {path.name}",
                        evidence=[f"Imports from: {v['to_module']}"],
                        recommendation="Remove direct import",
                        priority="urgent",
                        owner=AgentRole.BACKEND_DEV,
                    ))

        return signals

    async def _check_decimal_usage(self) -> List[ArchitectureSignal]:
        """Check for float usage where Decimal should be used."""
        signals = []
        backend_root = Path("/workspaces/Trucking_App/backend")

        # Patterns that suggest float misuse for money
        float_patterns = [
            "float(revenue",
            "float(cost",
            "float(profit",
            "float(rate",
            ": float",  # Type hint
            "-> float",  # Return type
        ]

        money_files = [
            backend_root / "app" / "engine" / "plan_generator.py",
            backend_root / "app" / "engine" / "optimizer.py",
            backend_root / "app" / "calibration",
            backend_root / "app" / "trust",
        ]

        for path in money_files:
            if path.is_dir():
                for py_file in path.glob("*.py"):
                    await self._scan_file_for_floats(py_file, float_patterns, signals)
            elif path.is_file() and path.exists():
                await self._scan_file_for_floats(path, float_patterns, signals)

        return signals

    async def _scan_file_for_floats(
        self,
        file_path: Path,
        patterns: List[str],
        signals: List[ArchitectureSignal],
    ):
        """Scan a file for float patterns."""
        try:
            content = file_path.read_text()
            for i, line in enumerate(content.split("\n"), 1):
                for pattern in patterns:
                    if pattern in line.lower() and "decimal" not in line.lower():
                        signals.append(ArchitectureSignal(
                            observation_type="decimal_violation",
                            severity=SignalSeverity.CONCERN,
                            summary=f"Possible float usage for money in {file_path.name}:{i}",
                            evidence=[f"Line {i}: {line.strip()[:80]}"],
                            recommendation="Use Decimal for all monetary values",
                            priority="soon",
                            owner=AgentRole.BACKEND_DEV,
                        ))
        except FileNotFoundError:
            pass

    async def _check_org_scoping(self) -> List[ArchitectureSignal]:
        """Check for queries missing org_id filter."""
        signals = []
        backend_root = Path("/workspaces/Trucking_App/backend")
        api_dir = backend_root / "app" / "api"

        if not api_dir.exists():
            return signals

        for py_file in api_dir.glob("*_routes.py"):
            try:
                content = py_file.read_text()

                # Check for queries without org_id
                if ".query(" in content and "org_id" not in content:
                    signals.append(ArchitectureSignal(
                        observation_type="org_scope_missing",
                        severity=SignalSeverity.WARNING,
                        summary=f"Possible missing org_id filter in {py_file.name}",
                        evidence=["Contains .query() but org_id not visible"],
                        recommendation="Ensure all queries filter by org_id",
                        priority="soon",
                        owner=AgentRole.BACKEND_DEV,
                    ))
            except FileNotFoundError:
                pass

        return signals

    async def _check_determinism(self) -> List[ArchitectureSignal]:
        """Check for nondeterministic patterns."""
        signals = []
        backend_root = Path("/workspaces/Trucking_App/backend")

        nondeterministic_patterns = [
            "random.random",
            "random.choice",
            "random.shuffle",
            "uuid.uuid4()",  # OK if used for IDs, but flag for review
            "datetime.now()",  # OK for timestamps, but flag if used in logic
        ]

        algorithm_paths = [
            backend_root / "app" / "engine",
            backend_root / "app" / "calibration",
            backend_root / "app" / "trust",
        ]

        for path in algorithm_paths:
            if path.is_dir():
                for py_file in path.glob("*.py"):
                    try:
                        content = py_file.read_text()
                        for pattern in nondeterministic_patterns:
                            if pattern in content:
                                signals.append(ArchitectureSignal(
                                    observation_type="determinism_issue",
                                    severity=SignalSeverity.WARNING,
                                    summary=f"Nondeterministic pattern in {py_file.name}: {pattern}",
                                    evidence=[f"Pattern: {pattern}"],
                                    recommendation="Ensure determinism or get human approval",
                                    priority="next_sprint",
                                    owner=AgentRole.ALGORITHM_ENGINEER,
                                ))
                    except FileNotFoundError:
                        pass

        return signals

    async def _check_entitlement_coverage(self) -> List[ArchitectureSignal]:
        """Check for premium endpoints without entitlement checks."""
        signals = []
        backend_root = Path("/workspaces/Trucking_App/backend")

        # Premium route files that should have entitlement checks
        premium_routes = [
            backend_root / "app" / "api" / "calibration_routes.py",
            backend_root / "app" / "api" / "trust_routes.py",
        ]

        for route_file in premium_routes:
            if route_file.exists():
                try:
                    content = route_file.read_text()
                    if "require_entitlement" not in content and "check_entitlement" not in content:
                        signals.append(ArchitectureSignal(
                            observation_type="entitlement_bypass",
                            severity=SignalSeverity.ALERT,
                            summary=f"Premium route file without entitlement check: {route_file.name}",
                            evidence=["No require_entitlement or check_entitlement found"],
                            recommendation="Add entitlement enforcement to all premium endpoints",
                            priority="urgent",
                            owner=AgentRole.BACKEND_DEV,
                        ))
                except FileNotFoundError:
                    pass

        return signals

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages requesting architecture review."""
        self.log(f"Architecture review requested by {message.from_agent.value}")

        # Run scan
        signals = await self.scan_codebase()

        # Summarize findings
        alert_count = sum(1 for s in signals if s.severity == SignalSeverity.ALERT)
        warning_count = sum(1 for s in signals if s.severity == SignalSeverity.WARNING)

        return AgentResponse(
            success=True,
            message=f"Scan complete: {alert_count} alerts, {warning_count} warnings",
            data={
                "signals": [
                    {
                        "type": s.observation_type,
                        "severity": s.severity.value,
                        "summary": s.summary,
                        "priority": s.priority,
                    }
                    for s in signals
                ]
            },
        )
