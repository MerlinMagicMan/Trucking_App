"""
Algorithm Engineer Agent - Owns optimization and learning algorithms.
"""

from typing import Dict, Any, List
from pathlib import Path
from decimal import Decimal

from ..types import (
    AgentRole, Task, Message, Module, AlgorithmProposal, EscalationReason,
)
from .base import ImplementerAgent, AgentResponse


class AlgorithmEngineerAgent(ImplementerAgent):
    """
    Algorithm Engineer owns optimization, calibration, and trust scoring.

    Guardian of the Learning Loop.

    Must follow:
    - Determinism rule (same inputs → same outputs)
    - Test vector requirement
    - Decimal-only money
    - HOS model versioning
    """

    def __init__(self):
        super().__init__(AgentRole.ALGORITHM_ENGINEER)
        self.backend_root = Path("/workspaces/Trucking_App/backend")

    async def propose_algorithm(
        self,
        name: str,
        description: str,
        module: Module,
    ) -> AlgorithmProposal:
        """
        Propose an algorithm change.

        All algorithm changes require test vectors.
        """
        self.log(f"Proposing algorithm: {name}")

        # Analyze determinism
        deterministic, nondeterminism_reason = self._check_determinism(description)

        # Identify decimal fields
        decimal_fields = self._identify_decimal_fields(description)

        # Check if escalation needed
        requires_escalation = self._needs_escalation(description, deterministic)

        return AlgorithmProposal(
            name=name,
            module=module,
            tier=self._get_tier(module),
            purpose=description,
            deterministic=deterministic,
            nondeterminism_reason=nondeterminism_reason,
            inputs=self._identify_inputs(description),
            outputs=self._identify_outputs(description),
            complexity_time=self._estimate_complexity(description),
            complexity_space="O(n)",  # Default
            search_space=self._estimate_search_space(description),
            pruning_strategy="Early termination on HOS violation",
            test_vectors=[],  # Must be filled by engineer
            decimal_fields=decimal_fields,
            requires_escalation=requires_escalation,
        )

    def _check_determinism(self, description: str) -> tuple[bool, str | None]:
        """Check if algorithm is deterministic."""
        desc_lower = description.lower()

        nondeterministic_patterns = [
            ("random", "Uses randomness"),
            ("sample", "Sampling may be nondeterministic"),
            ("shuffle", "Shuffling is nondeterministic"),
            ("probabilistic", "Probabilistic algorithms are nondeterministic"),
        ]

        for pattern, reason in nondeterministic_patterns:
            if pattern in desc_lower:
                return False, reason

        return True, None

    def _identify_decimal_fields(self, description: str) -> List[str]:
        """Identify fields that must use Decimal."""
        desc_lower = description.lower()
        decimal_fields = []

        money_keywords = [
            "revenue", "cost", "profit", "rate", "price",
            "fuel", "toll", "maintenance", "expense",
        ]

        for kw in money_keywords:
            if kw in desc_lower:
                decimal_fields.append(kw)

        return list(set(decimal_fields))

    def _get_tier(self, module: Module) -> str:
        """Get tier for module."""
        from ..context.product_boundaries import MODULE_BOUNDARIES
        boundary = MODULE_BOUNDARIES.get(module)
        return boundary.tier.value if boundary else "base"

    def _needs_escalation(self, description: str, deterministic: bool) -> bool:
        """Check if algorithm change needs human escalation."""
        desc_lower = description.lower()

        # Nondeterministic always needs escalation
        if not deterministic:
            return True

        # Trust/calibration changes need escalation
        if any(word in desc_lower for word in ["trust", "calibrat", "confidence"]):
            return True

        # HOS changes need escalation
        if "hos" in desc_lower or "hours of service" in desc_lower:
            return True

        return False

    def _identify_inputs(self, description: str) -> Dict[str, str]:
        """Identify algorithm inputs."""
        # Would be more sophisticated in production
        return {
            "loads": "List of available loads",
            "location": "Current truck location (lat, lon)",
            "hos_remaining": "HOS minutes remaining (drive, duty, cycle)",
        }

    def _identify_outputs(self, description: str) -> Dict[str, str]:
        """Identify algorithm outputs."""
        return {
            "plans": "List of Plan objects ranked by profit/day",
        }

    def _estimate_complexity(self, description: str) -> str:
        """Estimate time complexity."""
        desc_lower = description.lower()

        if "optim" in desc_lower:
            return "O(n! / pruning) - exponential base with aggressive pruning"
        elif "calibrat" in desc_lower:
            return "O(n) - linear in outcome count"
        elif "trust" in desc_lower:
            return "O(n) - linear in warning count"

        return "O(n)"

    def _estimate_search_space(self, description: str) -> str:
        """Estimate search space size."""
        desc_lower = description.lower()

        if "optim" in desc_lower or "plan" in desc_lower:
            return "n! permutations of loads, pruned by HOS/distance"

        return "Linear"

    def generate_test_vectors(self, proposal: AlgorithmProposal) -> str:
        """Generate test vector template."""
        return f'''"""
Test vectors for {proposal.name}

Module: {proposal.module.value}
Tier: {proposal.tier}

REQUIRED: All algorithm changes must ship with golden test vectors.
"""

import pytest
from decimal import Decimal


class Test{proposal.name.replace(" ", "")}:
    """Golden test vectors for {proposal.name}."""

    @pytest.mark.parametrize("test_case", [
        {{
            "name": "basic_single_load",
            "inputs": {{
                "location": (41.8781, -87.6298),  # Chicago
                "hos": {{"drive": 600, "duty": 840, "cycle": 4000}},
                "loads": [
                    {{"origin": (41.8, -87.6), "dest": (40.7, -74.0), "rate": Decimal("2500")}}
                ],
            }},
            "expected": {{
                "load_count": 1,
                "profit_per_day_min": Decimal("180.00"),
                "profit_per_day_max": Decimal("220.00"),
            }}
        }},
        {{
            "name": "multi_load_sequence",
            "inputs": {{
                # TODO: Add multi-load test case
            }},
            "expected": {{
                # TODO: Define expected output
            }}
        }},
        {{
            "name": "hos_constraint_violation",
            "inputs": {{
                "location": (41.8781, -87.6298),
                "hos": {{"drive": 60, "duty": 60, "cycle": 60}},  # Very limited HOS
                "loads": [
                    {{"origin": (41.8, -87.6), "dest": (40.7, -74.0), "rate": Decimal("2500")}}
                ],
            }},
            "expected": {{
                "load_count": 0,  # No feasible plans
            }}
        }},
    ])
    def test_golden_vectors(self, test_case):
        """Test algorithm against golden vectors."""
        # TODO: Implement test
        result = generate_plan(**test_case["inputs"])

        assert len(result.loads) == test_case["expected"]["load_count"]

    def test_determinism(self):
        """Same inputs must produce same outputs."""
        inputs = {{
            "location": (41.8781, -87.6298),
            "hos": {{"drive": 600, "duty": 840, "cycle": 4000}},
            "loads": [],
        }}

        result1 = generate_plan(**inputs)
        result2 = generate_plan(**inputs)

        assert result1 == result2, "Algorithm must be deterministic"

    def test_decimal_precision(self):
        """All monetary values must use Decimal."""
        result = calculate_profit(
            revenue=Decimal("1500.00"),
            costs=Decimal("500.00"),
        )

        assert isinstance(result, Decimal), "Profit must be Decimal"
'''

    async def implement(self, task: Task) -> AgentResponse:
        """Implement an algorithm task."""
        self.log(f"Implementing algorithm: {task.description}")

        proposal = await self.propose_algorithm(
            name=task.description,
            description=task.description,
            module=task.module or Module.TRUCK_PLAN,
        )

        if proposal.requires_escalation:
            return AgentResponse(
                success=False,
                message="Algorithm change requires human approval",
                data={"proposal": proposal.__dict__},
                requires_escalation=True,
                escalation_reason="Algorithm with trust/calibration implications",
            )

        test_vectors = self.generate_test_vectors(proposal)

        return AgentResponse(
            success=True,
            message="Algorithm proposal ready with test vectors",
            data={
                "proposal": {
                    "name": proposal.name,
                    "module": proposal.module.value,
                    "deterministic": proposal.deterministic,
                    "decimal_fields": proposal.decimal_fields,
                },
                "test_vectors_template": test_vectors,
            },
        )

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages from other agents."""
        self.log(f"Message from {message.from_agent.value}: {message.subject}")

        return AgentResponse(
            success=True,
            message="Message acknowledged",
        )
