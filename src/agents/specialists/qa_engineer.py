"""
QA Engineer Agent - Owns testing and quality gates.
"""

from typing import Dict, Any, List
from pathlib import Path
import re

from ..types import AgentRole, Task, Message, CodeReviewResult, VetoType
from .base import ImplementerAgent, AgentResponse


class QAEngineerAgent(ImplementerAgent):
    """
    QA Engineer owns testing, code review, and quality gates.

    Has VETO power on:
    - PR merge
    - Release

    Does NOT veto:
    - Product direction
    - Feature scope
    - Module placement
    """

    def __init__(self):
        super().__init__(AgentRole.QA_ENGINEER)
        self.backend_root = Path("/workspaces/Trucking_App/backend")
        self.frontend_root = Path("/workspaces/Trucking_App/frontend")

    async def review_code(self, file_path: str) -> CodeReviewResult:
        """
        Review code for quality issues.

        Returns blocking issues that prevent merge.
        """
        self.log(f"Reviewing: {file_path}")

        path = Path(file_path)
        if not path.exists():
            return CodeReviewResult(
                file_path=file_path,
                blocking_issues=[{"issue": "File not found"}],
                major_issues=[],
                minor_issues=[],
                merge_decision="BLOCKED",
                block_reasons=["File not found"],
            )

        content = path.read_text()

        blocking = []
        major = []
        minor = []

        # Check for blocking issues
        blocking.extend(self._check_decimal_violations(content, file_path))
        blocking.extend(self._check_import_violations(content, file_path))
        blocking.extend(self._check_entitlement_issues(content, file_path))
        blocking.extend(self._check_org_isolation(content, file_path))
        blocking.extend(self._check_determinism(content, file_path))

        # Check for major issues
        major.extend(self._check_error_handling(content, file_path))
        major.extend(self._check_type_safety(content, file_path))

        # Determine merge decision
        merge_decision = "BLOCKED" if blocking else "APPROVE"
        block_reasons = [issue["issue"] for issue in blocking]

        return CodeReviewResult(
            file_path=file_path,
            blocking_issues=blocking,
            major_issues=major,
            minor_issues=minor,
            merge_decision=merge_decision,
            block_reasons=block_reasons,
        )

    def _check_decimal_violations(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for float usage where Decimal should be used."""
        issues = []

        # Skip non-Python files
        if not file_path.endswith(".py"):
            return issues

        lines = content.split("\n")
        money_keywords = ["revenue", "cost", "profit", "rate", "price", "amount"]

        for i, line in enumerate(lines, 1):
            line_lower = line.lower()

            # Check for float type hints with money-related names
            for kw in money_keywords:
                if kw in line_lower and ": float" in line_lower:
                    issues.append({
                        "severity": "blocking",
                        "category": "decimal",
                        "location": f"Line {i}",
                        "issue": f"Float type hint for monetary value '{kw}'",
                        "fix": "Use Decimal instead of float for money",
                    })

            # Check for float() conversion of money
            if "float(" in line_lower:
                for kw in money_keywords:
                    if kw in line_lower:
                        issues.append({
                            "severity": "blocking",
                            "category": "decimal",
                            "location": f"Line {i}",
                            "issue": f"float() conversion of monetary value",
                            "fix": "Use Decimal() instead",
                        })

        return issues

    def _check_import_violations(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for base→premium import violations."""
        issues = []

        # Determine if this is a base module file
        base_paths = ["app/engine", "app/models/tenant", "app/models/plan"]
        is_base = any(bp in file_path for bp in base_paths)

        if not is_base:
            return issues

        premium_patterns = [
            "from app.calibration",
            "from app.trust",
            "from app.risk",
            "from app.analytics",
            "import app.calibration",
            "import app.trust",
        ]

        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            for pattern in premium_patterns:
                if pattern in line:
                    issues.append({
                        "severity": "blocking",
                        "category": "import_boundary",
                        "location": f"Line {i}",
                        "issue": f"Base module imports from premium: {pattern}",
                        "fix": "Remove direct import; use adapter pattern if needed",
                    })

        return issues

    def _check_entitlement_issues(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for premium endpoints without entitlement checks."""
        issues = []

        # Only check route files
        if "_routes.py" not in file_path:
            return issues

        # Check if this is a premium route file
        premium_route_files = ["calibration_routes", "trust_routes"]
        is_premium = any(prf in file_path for prf in premium_route_files)

        if is_premium:
            # Must have entitlement check
            if "require_entitlement" not in content and "check_entitlement" not in content:
                issues.append({
                    "severity": "blocking",
                    "category": "entitlement",
                    "location": "File level",
                    "issue": "Premium route file without entitlement enforcement",
                    "fix": "Add require_entitlement() check to all endpoints",
                })

        return issues

    def _check_org_isolation(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for queries without org_id filtering."""
        issues = []

        if not file_path.endswith(".py"):
            return issues

        # Look for queries that might be missing org_id
        if ".query(" in content or "select(" in content:
            if "org_id" not in content and "X-Org-Id" not in content:
                issues.append({
                    "severity": "blocking",
                    "category": "security",
                    "location": "File level",
                    "issue": "Database queries without visible org_id filtering",
                    "fix": "Ensure all queries filter by org_id",
                })

        return issues

    def _check_determinism(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for nondeterministic patterns in algorithm code."""
        issues = []

        # Only check algorithm-related files
        algorithm_paths = ["engine", "calibration", "trust", "optimizer"]
        is_algorithm = any(ap in file_path for ap in algorithm_paths)

        if not is_algorithm:
            return issues

        nondeterministic_patterns = [
            ("random.random()", "Unseeded random"),
            ("random.choice(", "Unseeded random choice"),
            ("random.shuffle(", "Unseeded random shuffle"),
        ]

        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            for pattern, reason in nondeterministic_patterns:
                if pattern in line and "seed" not in line.lower():
                    issues.append({
                        "severity": "blocking",
                        "category": "determinism",
                        "location": f"Line {i}",
                        "issue": f"Nondeterministic pattern: {reason}",
                        "fix": "Use seeded PRNG or remove randomness",
                    })

        return issues

    def _check_error_handling(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for missing error handling."""
        issues = []

        if not file_path.endswith(".py"):
            return issues

        # Check for bare except
        if "except:" in content and "except Exception" not in content:
            issues.append({
                "severity": "major",
                "category": "error_handling",
                "location": "File level",
                "issue": "Bare except clause found",
                "fix": "Use specific exception types",
            })

        return issues

    def _check_type_safety(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for type safety issues."""
        issues = []

        # Check TypeScript files
        if file_path.endswith(".ts") or file_path.endswith(".tsx"):
            if ": any" in content:
                count = content.count(": any")
                issues.append({
                    "severity": "major",
                    "category": "type_safety",
                    "location": "File level",
                    "issue": f"Found {count} uses of 'any' type",
                    "fix": "Replace with specific types",
                })

        return issues

    def generate_test_file(self, module_name: str, functions: List[str]) -> str:
        """Generate a test file template."""
        test_functions = "\n\n".join([
            f'''def test_{func}():
    """Test {func} function."""
    # TODO: Implement test
    pass''' for func in functions
        ])

        return f'''"""
Tests for {module_name}.

Coverage requirements:
- All public functions tested
- Edge cases covered
- Decimal precision verified
- Org isolation verified
"""

import pytest
from decimal import Decimal


{test_functions}


class TestDecimalPrecision:
    """Verify Decimal usage for monetary values."""

    def test_money_uses_decimal(self):
        """All monetary calculations must use Decimal."""
        # TODO: Implement
        pass


class TestOrgIsolation:
    """Verify org isolation."""

    def test_cannot_access_other_org_data(self):
        """Org A cannot access Org B's data."""
        # TODO: Implement
        pass
'''

    async def implement(self, task: Task) -> AgentResponse:
        """Implement a QA task (write tests)."""
        self.log(f"Writing tests for: {task.description}")

        # Generate test template
        test_code = self.generate_test_file(
            module_name=task.description,
            functions=["main_function"],  # Would be extracted from task
        )

        return AgentResponse(
            success=True,
            message="Test template generated",
            data={
                "test_code": test_code,
            },
        )

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle code review requests."""
        self.log(f"Review request from {message.from_agent.value}")

        if "review" in message.subject.lower():
            # Extract file path from message
            file_path = message.content.strip()
            review = await self.review_code(file_path)

            return AgentResponse(
                success=review.merge_decision == "APPROVE",
                message=f"Review complete: {review.merge_decision}",
                data={
                    "merge_decision": review.merge_decision,
                    "blocking_issues": review.blocking_issues,
                    "major_issues": review.major_issues,
                    "block_reasons": review.block_reasons,
                },
            )

        return AgentResponse(
            success=True,
            message="Message acknowledged",
        )
