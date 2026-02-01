"""
PlanGenerator - Multi-load plan generation (Phase 0 core)
Transforms "best next load" into "best multi-day plan"

This is the decision core of the Trucking Operating System.
Plans, not loads, are the unit of truth.
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.plan import Plan, LoadInPlan
from app.models.canonical import TruckSnapshot, CanonicalLoad, Recommendation, HOSSnapshot
from app.engine.optimizer import OptimizationEngine
from app.engine.economics import EconomicsEngine
from app.engine.time_engine import TimeEngine
from app.engine.risk_engine import RiskEngine
from app.engine.plan_explanations import generate_plan_explanations


class PlanGenerator:
    """
    Generates 2-3 strategically different multi-load plans
    Uses existing optimizer as building block (no rewriting)

    Deterministic: same input → same plans
    Shallow search: controlled graph expansion
    Explainable: every plan has ≥3 reasons
    """

    def __init__(
        self,
        optimization_engine: OptimizationEngine,
        economics_engine: EconomicsEngine
    ):
        self.optimization_engine = optimization_engine
        self.economics_engine = economics_engine
        self.time_engine = TimeEngine()
        self.risk_engine = RiskEngine()

    def generate_plans(
        self,
        truck: TruckSnapshot,
        planning_horizon_days: int = 7,
        max_plans: int = 3,
        radius_miles: int = 250,
        preloaded: Optional[List[CanonicalLoad]] = None,
    ) -> List[Plan]:
        """
        Generate 2-3 alternative multi-load plans

        Algorithm:
        1. Get top 5 first-load candidates from optimizer
        2. For each first load, simulate truck state after completion
        3. Get top 3 second-load candidates from new position
        4. Optionally chain a third load
        5. Build complete plans with timeline, financials, risks
        6. Select 2-3 strategically different plans

        Args:
            truck: Current truck state
            planning_horizon_days: Planning horizon (7-14 days)
            max_plans: Maximum plans to return (default 3)
            radius_miles: Search radius for loads

        Returns:
            List of 2-3 Plans sorted by profit_per_day descending
        """
        all_candidate_plans = []
        loads_analyzed_total = 0

        # Store preloaded for use in internal methods
        self._preloaded = preloaded

        # Step 1: Get top 5 first-load candidates
        first_load_recommendations = self._get_load_candidates(truck, top_n=5, radius_miles=radius_miles)

        if not first_load_recommendations:
            # No feasible first loads - return empty
            return []

        loads_analyzed_total += first_load_recommendations[1]  # Track loads analyzed

        # Step 2: Chain loads together
        for first_rec in first_load_recommendations[0]:
            # Get the full CanonicalLoad object
            first_load = self._get_load_from_recommendation(first_rec)
            if not first_load:
                continue

            # 2-load plans
            two_load_plans = self._build_two_load_plans(
                truck, first_load, first_rec, planning_horizon_days, radius_miles
            )
            all_candidate_plans.extend(two_load_plans)

            # 3-load plans (only if horizon >= 10 days)
            if planning_horizon_days >= 10:
                three_load_plans = self._build_three_load_plans(
                    truck, first_load, first_rec, planning_horizon_days, radius_miles
                )
                all_candidate_plans.extend(three_load_plans)

        # Step 3: Score and finalize all plans
        finalized_plans = []
        for candidate in all_candidate_plans:
            try:
                finalized_plan = self._finalize_plan(candidate, loads_analyzed_total)
                finalized_plans.append(finalized_plan)
            except Exception as e:
                # Skip plans that fail finalization
                continue

        if not finalized_plans:
            return []

        # Step 4: Sort by profit_per_day (descending) with plan_id as tiebreaker
        finalized_plans.sort(key=lambda p: (-p.profit_per_day_usd, str(p.plan_id)))

        # Step 5: Select strategically different plans
        diverse_plans = self._select_diverse_plans(finalized_plans, max_plans)

        return diverse_plans

    def _get_load_candidates(
        self,
        truck: TruckSnapshot,
        top_n: int,
        radius_miles: int
    ) -> Tuple[List[Recommendation], int]:
        """
        Get top N load candidates using existing optimizer

        Returns:
            (recommendations, loads_analyzed)
        """
        result = self.optimization_engine.optimize(
            truck, radius_miles=radius_miles, preloaded=self._preloaded
        )
        return result.recommendations[:top_n], result.loads_analyzed

    def _get_load_from_recommendation(self, recommendation: Recommendation) -> CanonicalLoad:
        """
        Get CanonicalLoad from Recommendation.
        Searches preloaded snapshot loads first, then falls back to connectors.
        """
        # Search preloaded loads first (snapshot-based)
        if self._preloaded:
            for load in self._preloaded:
                if load.id == recommendation.load_id:
                    return load

        # Fallback: search connectors
        for connector in self.optimization_engine.connectors:
            loads, _ = connector.search_loads(0, 0, radius_miles=5000)  # Wide search
            for load in loads:
                if load.id == recommendation.load_id:
                    return load
        return None

    def _simulate_truck_state_after_load(
        self,
        truck: TruckSnapshot,
        load: CanonicalLoad,
        hos_details: dict
    ) -> TruckSnapshot:
        """
        Simulate truck state after completing a load

        Returns:
            New TruckSnapshot at delivery location with updated HOS
        """
        # After a load + 10-hour rest, drive time resets to 11 hours
        # On-duty and cycle decrease by time used

        new_hos = HOSSnapshot(
            drive_remaining_min=660,  # Reset to 11 hours after rest
            on_duty_remaining_min=max(0, truck.hos.on_duty_remaining_min - hos_details["total_time_min"] + 600),  # Partial recovery
            cycle_remaining_min=max(0, truck.hos.cycle_remaining_min - hos_details["total_time_min"])
        )

        return TruckSnapshot(
            current_lat=load.delivery.lat,
            current_lng=load.delivery.lng,
            hos=new_hos
        )

    def _build_two_load_plans(
        self,
        truck: TruckSnapshot,
        first_load: CanonicalLoad,
        first_rec: Recommendation,
        planning_horizon_days: int,
        radius_miles: int
    ) -> List[dict]:
        """Build all 2-load plan candidates starting with first_load"""
        plans = []

        # Simulate truck after first load
        # After 10-hour rest: drive and on-duty reset, cycle decreases
        truck_after_first = TruckSnapshot(
            current_lat=first_rec.delivery_lat,
            current_lng=first_rec.delivery_lng,
            hos=HOSSnapshot(
                drive_remaining_min=660,  # Reset to 11 hours after 10-hour rest
                on_duty_remaining_min=840,  # Reset to 14 hours after 10-hour rest
                cycle_remaining_min=max(0, truck.hos.cycle_remaining_min - first_rec.estimated_total_time_min)
            )
        )

        # Get second load candidates
        second_recommendations, _ = self._get_load_candidates(truck_after_first, top_n=3, radius_miles=radius_miles)

        for second_rec in second_recommendations:
            second_load = self._get_load_from_recommendation(second_rec)
            if not second_load:
                continue

            # Create 2-load plan candidate
            plan_candidate = {
                "truck_snapshot": truck,
                "load_sequence": [first_load, second_load],
                "planning_horizon_days": planning_horizon_days
            }
            plans.append(plan_candidate)

        return plans

    def _build_three_load_plans(
        self,
        truck: TruckSnapshot,
        first_load: CanonicalLoad,
        first_rec: Recommendation,
        planning_horizon_days: int,
        radius_miles: int
    ) -> List[dict]:
        """Build all 3-load plan candidates (only for horizons >= 10 days)"""
        plans = []

        # Similar to 2-load, but chains one more
        # After 10-hour rest: drive and on-duty reset, cycle decreases
        truck_after_first = TruckSnapshot(
            current_lat=first_rec.delivery_lat,
            current_lng=first_rec.delivery_lng,
            hos=HOSSnapshot(
                drive_remaining_min=660,  # Reset to 11 hours after 10-hour rest
                on_duty_remaining_min=840,  # Reset to 14 hours after 10-hour rest
                cycle_remaining_min=max(0, truck.hos.cycle_remaining_min - first_rec.estimated_total_time_min)
            )
        )

        second_recommendations, _ = self._get_load_candidates(truck_after_first, top_n=2, radius_miles=radius_miles)

        for second_rec in second_recommendations:
            second_load = self._get_load_from_recommendation(second_rec)
            if not second_load:
                continue

            # Simulate after second load
            # After 10-hour rest: drive and on-duty reset, cycle decreases
            truck_after_second = TruckSnapshot(
                current_lat=second_rec.delivery_lat,
                current_lng=second_rec.delivery_lng,
                hos=HOSSnapshot(
                    drive_remaining_min=660,  # Reset to 11 hours after 10-hour rest
                    on_duty_remaining_min=840,  # Reset to 14 hours after 10-hour rest
                    cycle_remaining_min=max(0, truck_after_first.hos.cycle_remaining_min - second_rec.estimated_total_time_min)
                )
            )

            # Get third load candidates (only top 2)
            third_recommendations, _ = self._get_load_candidates(truck_after_second, top_n=2, radius_miles=radius_miles)

            for third_rec in third_recommendations:
                third_load = self._get_load_from_recommendation(third_rec)
                if not third_load:
                    continue

                plan_candidate = {
                    "truck_snapshot": truck,
                    "load_sequence": [first_load, second_load, third_load],
                    "planning_horizon_days": planning_horizon_days
                }
                plans.append(plan_candidate)

        return plans

    def _finalize_plan(self, candidate: dict, loads_analyzed: int) -> Plan:
        """
        Convert plan candidate into complete Plan with timeline, financials, risks, explanations
        """
        truck = candidate["truck_snapshot"]
        load_sequence = candidate["load_sequence"]
        horizon_days = candidate["planning_horizon_days"]

        # 1. Generate timeline
        time_blocks = self.time_engine.build_timeline(truck, load_sequence)

        # 2. Build LoadInPlan objects
        loads_in_plan = []
        for i, load in enumerate(load_sequence):
            # Get time blocks for this specific load
            load_time_blocks = [b for b in time_blocks if b.related_load_id == load.id]

            # Calculate deadhead for this load
            if i == 0:
                # First load - deadhead from truck position
                from app.engine.hos_checker import calculate_distance
                deadhead_miles = calculate_distance(
                    truck.current_lat, truck.current_lng,
                    load.pickup.lat, load.pickup.lng
                )
            else:
                # Subsequent loads - deadhead from previous delivery
                prev_load = load_sequence[i - 1]
                from app.engine.hos_checker import calculate_distance
                deadhead_miles = calculate_distance(
                    prev_load.delivery.lat, prev_load.delivery.lng,
                    load.pickup.lat, load.pickup.lng
                )

            load_in_plan = LoadInPlan(
                load=load,
                sequence_number=i + 1,
                deadhead_miles=deadhead_miles,
                revenue_usd=load.rate_total,
                estimated_fuel_cost_usd=0.0,  # Will be calculated by economics
                estimated_toll_cost_usd=0.0,
                net_revenue_usd=0.0,
                time_blocks=load_time_blocks
            )
            loads_in_plan.append(load_in_plan)

        # 3. Create initial plan (without financials)
        final_load = load_sequence[-1]
        plan = Plan(
            truck_snapshot=truck,
            planning_horizon_days=horizon_days,
            loads=loads_in_plan,
            time_blocks=time_blocks,
            end_location_lat=final_load.delivery.lat,
            end_location_lng=final_load.delivery.lng,
            end_location_name=f"{final_load.delivery.city}, {final_load.delivery.state}",
            total_revenue_usd=0.0,
            total_costs_usd=0.0,
            net_profit_usd=0.0,
            profit_per_day_usd=0.0,
            plan_score=0.0,  # Will be calculated
            confidence="medium",
            explanations=["Calculating plan metrics...", "Analyzing route strategy...", "Assessing financial outcome..."],  # Placeholder explanations
            loads_analyzed=loads_analyzed,
            plans_generated=1  # Will be updated later
        )

        # 4. Calculate economics
        plan = self.economics_engine.calculate_full_economics(plan)

        # 5. Assess risks
        risk_signals = self.risk_engine.assess_plan_risks(plan)
        plan.risk_signals = risk_signals

        # 6. Calculate plan score (simplified for Phase 0)
        plan.plan_score = min(100, max(0, int(plan.profit_per_day_usd / 5)))  # $500/day = 100 score

        # 7. Determine confidence
        risk_level = self.risk_engine.calculate_overall_risk_level(risk_signals)
        if risk_level == "low" and plan.profit_per_day_usd > 300:
            plan.confidence = "high"
        elif risk_level == "high":
            plan.confidence = "low"
        else:
            plan.confidence = "medium"

        # 8. Generate explanations
        explanations = generate_plan_explanations(plan)
        plan.explanations = explanations

        return plan

    def _select_diverse_plans(self, plans: List[Plan], max_plans: int) -> List[Plan]:
        """
        Select 2-3 strategically different plans from all candidates

        Strategy:
        - Plan #1: Highest profit_per_day (always)
        - Plan #2: Different first load OR different end location
        - Plan #3: Different strategy
        """
        if len(plans) <= max_plans:
            return plans

        selected = []

        # Always take #1 (highest profit_per_day)
        selected.append(plans[0])

        # Find plans that are strategically different
        for candidate in plans[1:]:
            if len(selected) >= max_plans:
                break

            if self._is_plan_diverse(candidate, selected):
                selected.append(candidate)

        # Fill remaining slots with next highest profit_per_day
        while len(selected) < max_plans and len(selected) < len(plans):
            for candidate in plans:
                if candidate not in selected:
                    selected.append(candidate)
                    break

        return selected[:max_plans]

    def _is_plan_diverse(self, candidate: Plan, existing: List[Plan]) -> bool:
        """
        Check if candidate plan is strategically different from existing plans

        Different means:
        - Different first load, OR
        - Different end location (>100 miles apart)
        """
        for existing_plan in existing:
            # Check first load
            candidate_first_load_id = candidate.loads[0].load.id
            existing_first_load_id = existing_plan.loads[0].load.id

            if candidate_first_load_id == existing_first_load_id:
                # Same first load - not diverse
                return False

            # Check end location
            from app.engine.hos_checker import calculate_distance
            end_distance = calculate_distance(
                candidate.end_location_lat, candidate.end_location_lng,
                existing_plan.end_location_lat, existing_plan.end_location_lng
            )

            if end_distance < 100:  # Within 100 miles
                # Too close - not diverse
                return False

        return True
