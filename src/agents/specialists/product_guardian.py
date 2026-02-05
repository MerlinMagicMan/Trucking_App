"""
Product Boundary Guardian Agent - Enforces monetization boundaries.
"""

from typing import Dict, Any

from ..types import (
    AgentRole, Task, Message, Module, Tier,
    ProductBoundaryReview, VetoType,
)
from ..context.product_boundaries import (
    MODULE_BOUNDARIES,
    get_module_for_path,
    check_import_violation,
)
from .base import ReviewerAgent, AgentResponse


class ProductGuardianAgent(ReviewerAgent):
    """
    Product Boundary Guardian enforces module boundaries and monetization.

    Has VETO power over feature placement.
    """

    def __init__(self):
        super().__init__(AgentRole.PRODUCT_GUARDIAN)

    async def review_feature(
        self,
        feature_name: str,
        proposed_module: Module,
        description: str,
    ) -> ProductBoundaryReview:
        """
        Review a feature for proper module placement.

        Returns a review with APPROVE, RELOCATE, or VETO decision.
        """
        self.log(f"Reviewing feature: {feature_name}")

        # Determine where feature belongs
        actual_module = self._determine_module(description)
        actual_tier = self._get_tier(actual_module)

        # Check for value leakage
        leakage_risk = self._assess_value_leakage(
            proposed_module,
            actual_module,
            description,
        )

        # Check import boundaries
        import_violation = self._check_import_boundary(proposed_module, description)

        # Determine decision
        decision, veto_reason, alternative = self._make_decision(
            proposed_module,
            actual_module,
            leakage_risk,
            import_violation,
        )

        return ProductBoundaryReview(
            feature=feature_name,
            proposed_location=proposed_module.value,
            belongs_to=actual_module,
            tier=actual_tier,
            rationale=self._get_rationale(actual_module, description),
            base_to_premium_imports=import_violation,
            adapter_pattern_required=self._needs_adapter(proposed_module, actual_module),
            value_leakage_risk=leakage_risk,
            base_tier_alternative=self._get_base_alternative(actual_module, description),
            upgrade_driver=self._get_upgrade_driver(actual_module),
            decision=decision,
            veto_reason=veto_reason if decision == "VETO" else None,
            value_leaked=self._describe_leaked_value(actual_module) if decision == "VETO" else None,
            alternative=alternative if decision in ("VETO", "RELOCATE") else None,
        )

    def _determine_module(self, description: str) -> Module:
        """Determine which module a feature belongs to."""
        desc_lower = description.lower()

        # Learning loop features -> TRUCK_LEARN
        if any(word in desc_lower for word in [
            "calibrat", "trust score", "confidence", "bias correction",
            "learn", "improve prediction", "adjustment factor",
        ]):
            return Module.TRUCK_LEARN

        # Real integrations -> TRUCK_CONNECT
        if any(word in desc_lower for word in [
            "dat", "truckstop", "load board", "api integration",
            "real-time loads", "market feed",
        ]):
            return Module.TRUCK_CONNECT

        # Analytics -> TRUCK_INSIGHT
        if any(word in desc_lower for word in [
            "analytic", "pattern", "trend", "intelligence",
            "lane stat", "market stat", "negotiation",
        ]):
            return Module.TRUCK_INSIGHT

        # Fleet -> TRUCK_FLEET
        if any(word in desc_lower for word in [
            "fleet", "multi-truck", "dispatcher", "multiple vehicles",
        ]):
            return Module.TRUCK_FLEET

        # Outcome tracking (no learning) -> TRUCK_TRACK
        if any(word in desc_lower for word in [
            "outcome", "actual", "record", "history", "predicted vs",
        ]):
            return Module.TRUCK_TRACK

        # Plan generation -> TRUCK_PLAN
        if any(word in desc_lower for word in [
            "plan", "generat", "optim", "load sequence",
        ]):
            return Module.TRUCK_PLAN

        return Module.TRUCK_CORE

    def _get_tier(self, module: Module) -> Tier:
        """Get the tier for a module."""
        boundary = MODULE_BOUNDARIES.get(module)
        if boundary:
            return boundary.tier
        return Tier.BASE

    def _assess_value_leakage(
        self,
        proposed: Module,
        actual: Module,
        description: str,
    ) -> str:
        """Assess the value leakage risk."""
        if proposed == actual:
            return "none"

        proposed_tier = self._get_tier(proposed)
        actual_tier = self._get_tier(actual)

        # Premium feature in base tier = critical
        if actual_tier == Tier.PREMIUM and proposed_tier == Tier.BASE:
            return "critical"

        # Enterprise feature in premium = high
        if actual_tier == Tier.ENTERPRISE and proposed_tier == Tier.PREMIUM:
            return "high"

        # Same tier but wrong module = low
        if proposed_tier == actual_tier:
            return "low"

        return "medium"

    def _check_import_boundary(self, proposed: Module, description: str) -> bool:
        """Check if the feature would create import boundary violations."""
        boundary = MODULE_BOUNDARIES.get(proposed)
        if not boundary:
            return False

        # Check if description implies importing from forbidden modules
        desc_lower = description.lower()

        for forbidden in boundary.cannot_import_from:
            forbidden_boundary = MODULE_BOUNDARIES.get(forbidden)
            if forbidden_boundary:
                # Check for keywords that suggest importing
                for path in forbidden_boundary.backend_paths:
                    module_name = path.split("/")[-1].replace(".py", "").replace("/", "")
                    if module_name in desc_lower:
                        return True

        return False

    def _make_decision(
        self,
        proposed: Module,
        actual: Module,
        leakage_risk: str,
        import_violation: bool,
    ) -> tuple[str, str | None, str | None]:
        """Make the review decision."""
        # Import violation = VETO
        if import_violation:
            return (
                "VETO",
                "Creates base→premium import boundary violation",
                f"Use adapter pattern or move to {actual.value}",
            )

        # Critical leakage = VETO
        if leakage_risk == "critical":
            return (
                "VETO",
                f"Feature belongs in {actual.value} (premium), not {proposed.value} (base)",
                f"Move to {actual.value} module with entitlement gating",
            )

        # High leakage = VETO
        if leakage_risk == "high":
            return (
                "VETO",
                f"Feature belongs in {actual.value}, not {proposed.value}",
                f"Move to {actual.value} module",
            )

        # Medium leakage = RELOCATE
        if leakage_risk == "medium":
            return (
                "RELOCATE",
                None,
                f"Relocate to {actual.value} module",
            )

        # All clear
        return ("APPROVE", None, None)

    def _needs_adapter(self, proposed: Module, actual: Module) -> bool:
        """Check if adapter pattern is needed."""
        proposed_tier = self._get_tier(proposed)
        actual_tier = self._get_tier(actual)

        # Base module wanting premium data needs adapter
        return proposed_tier == Tier.BASE and actual_tier in {Tier.PREMIUM, Tier.ENTERPRISE}

    def _get_rationale(self, module: Module, description: str) -> str:
        """Get rationale for module assignment."""
        boundary = MODULE_BOUNDARIES.get(module)
        if boundary:
            return boundary.description
        return "Core functionality"

    def _get_base_alternative(self, module: Module, description: str) -> str | None:
        """Get what base tier users get instead."""
        if module == Module.TRUCK_LEARN:
            return "View raw predicted vs actual data (no auto-calibration)"
        elif module == Module.TRUCK_CONNECT:
            return "Manual load entry or CSV import"
        elif module == Module.TRUCK_INSIGHT:
            return "Basic plan comparison without market intelligence"
        elif module == Module.TRUCK_FLEET:
            return "Single-truck mode only"
        return None

    def _get_upgrade_driver(self, module: Module) -> str | None:
        """Get the pain point that drives upgrade."""
        if module == Module.TRUCK_LEARN:
            return "Predictions don't improve over time without calibration"
        elif module == Module.TRUCK_CONNECT:
            return "Manual load entry is slow and error-prone"
        elif module == Module.TRUCK_INSIGHT:
            return "Missing market context for negotiations"
        elif module == Module.TRUCK_FLEET:
            return "Can't optimize across multiple trucks"
        return None

    def _describe_leaked_value(self, module: Module) -> str | None:
        """Describe what premium value would be leaked."""
        if module == Module.TRUCK_LEARN:
            return "The learning loop that improves predictions - the core moat"
        elif module == Module.TRUCK_CONNECT:
            return "Real-time load board integration"
        elif module == Module.TRUCK_INSIGHT:
            return "Market intelligence and analytics"
        elif module == Module.TRUCK_FLEET:
            return "Fleet-level optimization capabilities"
        return None

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages requesting review."""
        self.log(f"Review request from {message.from_agent.value}")

        # Parse feature details from message
        # In a real implementation, this would parse structured data

        return AgentResponse(
            success=True,
            message="Review completed. See data for decision.",
            data={"decision": "APPROVE"},  # Placeholder
        )
