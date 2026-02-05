"""
Tests for Stratum 6A: Confidence Weighting

Verifies:
- Decimal discipline (no floats)
- Unknown confidence = no influence
- Determinism
- Bounded multiplier [0.50, 1.00]
"""
import pytest
from decimal import Decimal

from app.trust.weighting import (
    compute_confidence_multiplier,
    compute_weighted_score,
    get_confidence_label,
    HALF,
    HUNDRED,
    MIN_MULTIPLIER,
    MAX_MULTIPLIER,
)


class TestConfidenceMultiplier:
    """Tests for compute_confidence_multiplier()"""

    def test_high_confidence_100(self):
        """Score 100 → multiplier 1.00"""
        result = compute_confidence_multiplier(100)
        assert result == Decimal("1.0")
        assert isinstance(result, Decimal)

    def test_high_confidence_80(self):
        """Score 80 → multiplier 0.90"""
        result = compute_confidence_multiplier(80)
        assert result == Decimal("0.9")

    def test_medium_confidence_55(self):
        """Score 55 → multiplier 0.775"""
        result = compute_confidence_multiplier(55)
        assert result == Decimal("0.775")

    def test_medium_confidence_79(self):
        """Score 79 → multiplier 0.895"""
        result = compute_confidence_multiplier(79)
        assert result == Decimal("0.895")

    def test_low_confidence_54(self):
        """Score 54 → multiplier 0.77"""
        result = compute_confidence_multiplier(54)
        assert result == Decimal("0.77")

    def test_low_confidence_0(self):
        """Score 0 → multiplier 0.50 (minimum)"""
        result = compute_confidence_multiplier(0)
        assert result == Decimal("0.5")

    def test_unknown_confidence_none(self):
        """Unknown (None) → multiplier 1.00 (no influence)"""
        result = compute_confidence_multiplier(None)
        assert result == Decimal("1.0")

    def test_clamped_above_100(self):
        """Score >100 clamped to 100 → multiplier 1.00"""
        result = compute_confidence_multiplier(150)
        assert result == Decimal("1.0")

    def test_clamped_below_0(self):
        """Score <0 clamped to 0 → multiplier 0.50"""
        result = compute_confidence_multiplier(-10)
        assert result == Decimal("0.5")

    def test_multiplier_always_decimal(self):
        """All results must be Decimal type"""
        for score in [None, 0, 25, 50, 75, 100]:
            result = compute_confidence_multiplier(score)
            assert isinstance(result, Decimal), f"Score {score} returned {type(result)}"

    def test_multiplier_bounded(self):
        """Multiplier always in [0.50, 1.00]"""
        for score in range(-10, 120):
            result = compute_confidence_multiplier(score)
            assert MIN_MULTIPLIER <= result <= MAX_MULTIPLIER, f"Score {score} → {result}"


class TestWeightedScore:
    """Tests for compute_weighted_score()"""

    def test_high_confidence_full_weight(self):
        """High confidence (100) gives full weight"""
        profit = Decimal("500.00")
        result = compute_weighted_score(profit, 100)
        assert result == Decimal("500.00")

    def test_low_confidence_reduced_weight(self):
        """Low confidence (0) gives half weight"""
        profit = Decimal("500.00")
        result = compute_weighted_score(profit, 0)
        assert result == Decimal("250.00")

    def test_medium_confidence_partial_weight(self):
        """Medium confidence (50) gives 0.75 weight"""
        profit = Decimal("400.00")
        result = compute_weighted_score(profit, 50)
        # multiplier = 0.5 + 0.5 * 0.5 = 0.75
        assert result == Decimal("300.00")

    def test_unknown_confidence_unchanged(self):
        """Unknown confidence returns profit unchanged"""
        profit = Decimal("750.00")
        result = compute_weighted_score(profit, None)
        assert result == profit
        assert result == Decimal("750.00")

    def test_result_is_decimal(self):
        """Result must be Decimal type"""
        result = compute_weighted_score(Decimal("100.00"), 80)
        assert isinstance(result, Decimal)

    def test_determinism_same_inputs(self):
        """Same inputs must produce identical outputs"""
        profit = Decimal("456.78")
        confidence = 67

        result1 = compute_weighted_score(profit, confidence)
        result2 = compute_weighted_score(profit, confidence)

        assert result1 == result2
        assert result1 is not result2  # Different objects, same value


class TestConfidenceLabel:
    """Tests for get_confidence_label()"""

    def test_high_at_80(self):
        assert get_confidence_label(80) == "high"

    def test_high_at_100(self):
        assert get_confidence_label(100) == "high"

    def test_medium_at_55(self):
        assert get_confidence_label(55) == "medium"

    def test_medium_at_79(self):
        assert get_confidence_label(79) == "medium"

    def test_low_at_54(self):
        assert get_confidence_label(54) == "low"

    def test_low_at_0(self):
        assert get_confidence_label(0) == "low"

    def test_unknown_none(self):
        assert get_confidence_label(None) == "unknown"


class TestDecimalDiscipline:
    """Verify no float contamination"""

    def test_constants_are_decimal(self):
        """Module constants must be Decimal"""
        assert isinstance(HALF, Decimal)
        assert isinstance(HUNDRED, Decimal)
        assert isinstance(MIN_MULTIPLIER, Decimal)
        assert isinstance(MAX_MULTIPLIER, Decimal)

    def test_no_float_in_calculation(self):
        """Intermediate calculations must stay Decimal"""
        # This would fail if floats were used internally
        profit = Decimal("123.456789012345")
        result = compute_weighted_score(profit, 73)

        # Verify precision is maintained (floats would lose precision)
        assert isinstance(result, Decimal)
        # The result should be exact Decimal arithmetic
        expected_multiplier = Decimal("0.5") + (Decimal("0.5") * Decimal("73") / Decimal("100"))
        expected = profit * expected_multiplier
        assert result == expected


class TestDeterminism:
    """Verify deterministic behavior"""

    def test_multiplier_determinism(self):
        """compute_confidence_multiplier is deterministic"""
        for score in [None, 0, 25, 50, 75, 100]:
            results = [compute_confidence_multiplier(score) for _ in range(10)]
            assert all(r == results[0] for r in results), f"Non-deterministic for score {score}"

    def test_weighted_score_determinism(self):
        """compute_weighted_score is deterministic"""
        test_cases = [
            (Decimal("100.00"), 50),
            (Decimal("999.99"), 80),
            (Decimal("0.01"), 10),
            (Decimal("500.00"), None),
        ]
        for profit, confidence in test_cases:
            results = [compute_weighted_score(profit, confidence) for _ in range(10)]
            assert all(r == results[0] for r in results), f"Non-deterministic for ({profit}, {confidence})"


class TestRankingAdapter:
    """Tests for plan_ranker module"""

    def test_rank_plans_empty_list(self):
        """Empty list returns empty list"""
        from app.engine.plan_ranker import rank_plans
        result = rank_plans([])
        assert result == []

    def test_rank_plans_without_weighting(self):
        """Without weighting_fn, ranks by profit_per_day only"""
        from app.engine.plan_ranker import rank_plans
        from unittest.mock import MagicMock

        # Create mock plans
        plan1 = MagicMock()
        plan1.profit_per_day_usd = 300.0
        plan1.plan_id = "plan-1"
        plan1.confidence_score = 90

        plan2 = MagicMock()
        plan2.profit_per_day_usd = 500.0
        plan2.plan_id = "plan-2"
        plan2.confidence_score = 50

        plan3 = MagicMock()
        plan3.profit_per_day_usd = 400.0
        plan3.plan_id = "plan-3"
        plan3.confidence_score = 80

        plans = [plan1, plan2, plan3]
        result = rank_plans(plans, weighting_fn=None)

        # Should be sorted by profit_per_day descending
        assert result[0].plan_id == "plan-2"  # $500
        assert result[1].plan_id == "plan-3"  # $400
        assert result[2].plan_id == "plan-1"  # $300

    def test_rank_plans_with_weighting(self):
        """With weighting_fn, ranks by weighted score"""
        from app.engine.plan_ranker import rank_plans
        from unittest.mock import MagicMock

        # Create mock plans
        plan1 = MagicMock()
        plan1.profit_per_day_usd = 300.0
        plan1.plan_id = "plan-1"
        plan1.confidence_score = 100  # High confidence → $300 * 1.0 = $300

        plan2 = MagicMock()
        plan2.profit_per_day_usd = 500.0
        plan2.plan_id = "plan-2"
        plan2.confidence_score = 0  # Low confidence → $500 * 0.5 = $250

        plans = [plan1, plan2]
        result = rank_plans(plans, weighting_fn=compute_weighted_score)

        # plan1 ($300 weighted) should beat plan2 ($250 weighted)
        assert result[0].plan_id == "plan-1"
        assert result[1].plan_id == "plan-2"

    def test_rank_plans_unknown_confidence_unchanged(self):
        """Unknown confidence (None) doesn't change relative ranking"""
        from app.engine.plan_ranker import rank_plans
        from unittest.mock import MagicMock

        plan1 = MagicMock()
        plan1.profit_per_day_usd = 300.0
        plan1.plan_id = "plan-1"
        plan1.confidence_score = None  # Unknown → multiplier 1.0 → $300

        plan2 = MagicMock()
        plan2.profit_per_day_usd = 250.0
        plan2.plan_id = "plan-2"
        plan2.confidence_score = None  # Unknown → multiplier 1.0 → $250

        plans = [plan1, plan2]
        result = rank_plans(plans, weighting_fn=compute_weighted_score)

        # Same as profit-only ranking
        assert result[0].plan_id == "plan-1"
        assert result[1].plan_id == "plan-2"

    def test_rank_plans_does_not_mutate_input(self):
        """rank_plans returns new list, doesn't mutate input"""
        from app.engine.plan_ranker import rank_plans
        from unittest.mock import MagicMock

        plan1 = MagicMock()
        plan1.profit_per_day_usd = 100.0
        plan1.plan_id = "plan-1"

        plan2 = MagicMock()
        plan2.profit_per_day_usd = 200.0
        plan2.plan_id = "plan-2"

        original = [plan1, plan2]
        original_order = [p.plan_id for p in original]

        result = rank_plans(original, weighting_fn=None)

        # Original unchanged
        assert [p.plan_id for p in original] == original_order
        # Result is different object
        assert result is not original

    def test_rank_plans_deterministic_tiebreaker(self):
        """Plans with same score are sorted by plan_id for determinism"""
        from app.engine.plan_ranker import rank_plans
        from unittest.mock import MagicMock

        plan1 = MagicMock()
        plan1.profit_per_day_usd = 300.0
        plan1.plan_id = "plan-b"

        plan2 = MagicMock()
        plan2.profit_per_day_usd = 300.0
        plan2.plan_id = "plan-a"

        plans = [plan1, plan2]
        result = rank_plans(plans, weighting_fn=None)

        # Same profit → alphabetical by plan_id
        assert result[0].plan_id == "plan-a"
        assert result[1].plan_id == "plan-b"


class TestImportBoundary:
    """Verify import boundaries are not violated"""

    def test_plan_generator_has_no_trust_imports(self):
        """plan_generator.py must not import from app.trust"""
        import ast
        from pathlib import Path

        plan_generator_path = Path(__file__).parent.parent / "app" / "engine" / "plan_generator.py"
        with open(plan_generator_path) as f:
            source = f.read()

        tree = ast.parse(source)
        trust_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "trust" in alias.name:
                        trust_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "trust" in node.module:
                    trust_imports.append(node.module)

        assert trust_imports == [], f"plan_generator.py has trust imports: {trust_imports}"

    def test_plan_ranker_has_no_trust_imports(self):
        """plan_ranker.py must not import from app.trust"""
        import ast
        from pathlib import Path

        plan_ranker_path = Path(__file__).parent.parent / "app" / "engine" / "plan_ranker.py"
        with open(plan_ranker_path) as f:
            source = f.read()

        tree = ast.parse(source)
        trust_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "trust" in alias.name:
                        trust_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "trust" in node.module:
                    trust_imports.append(node.module)

        assert trust_imports == [], f"plan_ranker.py has trust imports: {trust_imports}"

    def test_weighting_module_in_trust_directory(self):
        """weighting.py must be in app/trust/ (TruckLEARN module)"""
        from pathlib import Path

        weighting_path = Path(__file__).parent.parent / "app" / "trust" / "weighting.py"
        assert weighting_path.exists(), "weighting.py must be in app/trust/"


class TestTierSeparation:
    """Verify tier-based behavior"""

    def test_base_tier_ranking_uses_profit_only(self):
        """Base tier should rank by profit_per_day without weighting"""
        from app.engine.plan_ranker import rank_plans
        from unittest.mock import MagicMock

        # Create plans where weighting would change order
        plan1 = MagicMock()
        plan1.profit_per_day_usd = 400.0
        plan1.plan_id = "plan-1"
        plan1.confidence_score = 0  # Low confidence

        plan2 = MagicMock()
        plan2.profit_per_day_usd = 300.0
        plan2.plan_id = "plan-2"
        plan2.confidence_score = 100  # High confidence

        # Base tier: weighting_fn=None
        result = rank_plans([plan1, plan2], weighting_fn=None)

        # Profit-only: $400 beats $300
        assert result[0].plan_id == "plan-1"

    def test_premium_tier_ranking_uses_weighted_score(self):
        """Premium tier should rank by confidence-weighted score"""
        from app.engine.plan_ranker import rank_plans
        from unittest.mock import MagicMock

        # Same plans as above
        plan1 = MagicMock()
        plan1.profit_per_day_usd = 400.0
        plan1.plan_id = "plan-1"
        plan1.confidence_score = 0  # Low → $400 * 0.5 = $200

        plan2 = MagicMock()
        plan2.profit_per_day_usd = 300.0
        plan2.plan_id = "plan-2"
        plan2.confidence_score = 100  # High → $300 * 1.0 = $300

        # Premium tier: weighting_fn=compute_weighted_score
        result = rank_plans([plan1, plan2], weighting_fn=compute_weighted_score)

        # Weighted: $300 beats $200
        assert result[0].plan_id == "plan-2"
