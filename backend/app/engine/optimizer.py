"""
Main recommendation engine optimizer
Orchestrates load fetching, HOS checking, scoring, and ranking
"""
from typing import List, Tuple
from datetime import datetime, timedelta

from app.models.canonical import (
    TruckSnapshot, CanonicalLoad, Recommendation,
    OptimizeResponse, ForwardLook, TimelineEvent
)
from app.engine.hos_checker import check_hos_feasibility, get_infeasibility_reason
from app.engine.scoring import (
    calculate_reload_score, calculate_confidence,
    calculate_appointment_risk_penalty, is_reefer_hub, is_strong_time_band
)
from app.engine.explanations import generate_explanations
from app.connectors.base import BaseConnector


class OptimizationEngine:
    """
    Core optimization engine
    Decision-support system for single-truck reefer operations
    """

    def __init__(self, connectors: List[BaseConnector]):
        self.connectors = connectors

    def optimize(self, truck: TruckSnapshot, radius_miles: int = 250) -> OptimizeResponse:
        """
        Main optimization flow:
        1. Fetch loads from all connectors
        2. Filter for HOS feasibility (HARD CONSTRAINT)
        3. Score and rank feasible loads
        4. Return top 3 (or fewer if <3 feasible)
        5. Generate forward-look timeline

        Returns deterministic results for same input
        """
        # Step 1: Fetch loads from all connectors
        all_loads = []
        connector_metadata = []

        for connector in self.connectors:
            try:
                loads, metadata = connector.fetch_and_normalize(
                    truck.current_lat,
                    truck.current_lng,
                    radius_miles
                )
                all_loads.extend(loads)
                connector_metadata.append(metadata)
            except Exception as e:
                # Log error but continue with other connectors
                connector_metadata.append({
                    "connector": connector.name,
                    "status": "error",
                    "error": str(e)
                })

        # Sort loads by ID for deterministic ordering
        all_loads.sort(key=lambda x: x.id)

        loads_analyzed = len(all_loads)

        # Step 2: Filter for HOS feasibility
        feasible_loads_with_details = []

        for load in all_loads:
            is_feasible, hos_details = check_hos_feasibility(truck, load)

            if is_feasible:
                feasible_loads_with_details.append((load, hos_details))

        loads_feasible = len(feasible_loads_with_details)

        # Step 3: Score and rank feasible loads
        scored_loads = []

        for load, hos_details in feasible_loads_with_details:
            # Check data completeness
            has_delivery_window = (
                load.delivery.window_start is not None and
                load.delivery.window_end is not None
            )
            has_pickup_window = (
                load.pickup.window_start is not None and
                load.pickup.window_end is not None
            )
            has_miles_data = load.miles is not None

            # Skip loads without critical data
            if not has_delivery_window:
                continue

            # Calculate reload score
            reload_score = calculate_reload_score(
                deadhead_miles=hos_details["deadhead_miles"],
                arrival_at_delivery=hos_details["arrival_at_delivery"],
                delivery_city=load.delivery.city,
                delivery_state=load.delivery.state,
                delivery_window_start=load.delivery.window_start,
                delivery_window_end=load.delivery.window_end,
                has_complete_data=(has_delivery_window and has_pickup_window and has_miles_data)
            )

            # Check reefer hub status
            is_hub, _ = is_reefer_hub(load.delivery.city, load.delivery.state)
            is_strong_time, _ = is_strong_time_band(hos_details["arrival_at_delivery"])

            # Calculate appointment risk
            _, risk_level = calculate_appointment_risk_penalty(
                hos_details["arrival_at_delivery"],
                load.delivery.window_start,
                load.delivery.window_end
            )

            # Calculate confidence
            confidence = calculate_confidence(
                has_delivery_window=has_delivery_window,
                has_pickup_window=has_pickup_window,
                has_miles_data=has_miles_data,
                appointment_risk_level=risk_level,
                is_reefer_hub=is_hub
            )

            # Generate explanations
            explanations = generate_explanations(
                deadhead_miles=hos_details["deadhead_miles"],
                loaded_miles=hos_details["loaded_miles"],
                rate_total=load.rate_total,
                arrival_at_pickup=hos_details["arrival_at_pickup"],
                arrival_at_delivery=hos_details["arrival_at_delivery"],
                pickup_window_start=load.pickup.window_start or hos_details["arrival_at_pickup"],
                pickup_window_end=load.pickup.window_end or (hos_details["arrival_at_pickup"] + timedelta(hours=4)),
                delivery_window_start=load.delivery.window_start,
                delivery_window_end=load.delivery.window_end,
                delivery_city=load.delivery.city,
                delivery_state=load.delivery.state,
                is_reefer_hub=is_hub,
                is_strong_time_band=is_strong_time,
                reload_score=reload_score,
                hos_details=hos_details
            )

            scored_loads.append({
                "load": load,
                "hos_details": hos_details,
                "reload_score": reload_score,
                "confidence": confidence,
                "explanations": explanations
            })

        # Step 4: Sort by reload_score (descending) and take top 3
        # Secondary sort by load ID for determinism when scores are equal
        scored_loads.sort(key=lambda x: (-x["reload_score"], x["load"].id))
        top_loads = scored_loads[:3]

        # Step 5: Create Recommendation objects
        recommendations = []
        for rank, item in enumerate(top_loads, start=1):
            load = item["load"]
            hos_details = item["hos_details"]

            recommendation = Recommendation(
                load_id=load.id,
                rank=rank,
                hos_feasible=True,  # Always true since we filtered
                arrival_at_pickup=hos_details["arrival_at_pickup"],
                arrival_at_delivery=hos_details["arrival_at_delivery"],
                reload_score=item["reload_score"],
                confidence=item["confidence"],
                explanations=item["explanations"],
                deadhead_miles=hos_details["deadhead_miles"],
                total_miles=hos_details["total_miles"],
                estimated_total_time_min=hos_details["total_time_min"],
                # Phase 0: Add delivery location for plan chaining
                delivery_lat=load.delivery.lat,
                delivery_lng=load.delivery.lng
            )
            recommendations.append(recommendation)

        # Step 6: Generate warnings
        warnings = []
        if loads_feasible < 3:
            if loads_feasible == 0:
                warnings.append(
                    f"No HOS-feasible loads found within {radius_miles} miles. "
                    f"Analyzed {loads_analyzed} loads but none fit within available HOS."
                )
            else:
                warnings.append(
                    f"Only {loads_feasible} HOS-feasible load(s) found (need 3 for full recommendations). "
                    f"Consider wider search radius or rest break."
                )

        if truck.hos.drive_remaining_min < 300:  # Less than 5 hours
            warnings.append(
                f"Low drive time remaining ({truck.hos.drive_remaining_min} minutes). "
                f"Consider planning a rest break soon."
            )

        # Step 7: Generate forward-look timeline (for top recommendation)
        forward_look = None
        if recommendations:
            forward_look = self._generate_forward_look(
                truck, top_loads[0]["load"], top_loads[0]["hos_details"]
            )

        return OptimizeResponse(
            snapshot_id=truck.snapshot_id,
            recommendations=recommendations,
            forward_look=forward_look,
            warnings=warnings,
            loads_analyzed=loads_analyzed,
            loads_feasible=loads_feasible
        )

    def _generate_forward_look(
        self,
        truck: TruckSnapshot,
        load: CanonicalLoad,
        hos_details: dict
    ) -> ForwardLook:
        """
        Generate 24-48 hour forward-looking timeline
        Shows what happens if driver takes the recommended load
        """
        events = []
        now = datetime.utcnow()

        # Current position
        events.append(TimelineEvent(
            timestamp=now,
            event_type="current",
            description="Current position",
            location=f"Lat: {truck.current_lat:.4f}, Lng: {truck.current_lng:.4f}"
        ))

        # Arrive at pickup
        events.append(TimelineEvent(
            timestamp=hos_details["arrival_at_pickup"],
            event_type="arrive_pickup",
            description=f"Arrive at pickup ({int(hos_details['deadhead_miles'])} miles)",
            location=f"{load.pickup.city}, {load.pickup.state}"
        ))

        # Depart pickup (after loading)
        depart_pickup = hos_details["arrival_at_pickup"] + timedelta(hours=1.5)
        events.append(TimelineEvent(
            timestamp=depart_pickup,
            event_type="depart_pickup",
            description="Depart pickup (loaded)",
            location=f"{load.pickup.city}, {load.pickup.state}"
        ))

        # Arrive at delivery
        events.append(TimelineEvent(
            timestamp=hos_details["arrival_at_delivery"],
            event_type="arrive_delivery",
            description=f"Arrive at delivery ({int(hos_details['loaded_miles'])} miles)",
            location=f"{load.delivery.city}, {load.delivery.state}"
        ))

        # Available for reload (after unloading)
        available_reload = hos_details["arrival_at_delivery"] + timedelta(hours=1.5)
        is_hub, _ = is_reefer_hub(load.delivery.city, load.delivery.state)
        reload_desc = "Available for reload in major reefer hub" if is_hub else "Available for reload"

        events.append(TimelineEvent(
            timestamp=available_reload,
            event_type="available_reload",
            description=reload_desc,
            location=f"{load.delivery.city}, {load.delivery.state}"
        ))

        # Market assessment
        market_assessment = None
        if is_hub:
            market_assessment = (
                f"{load.delivery.city} is a major reefer hub with typically strong outbound freight. "
                f"Expected reload opportunities throughout the day."
            )
        else:
            market_assessment = (
                f"Reload opportunities in {load.delivery.city} vary by time and season. "
                f"Monitor load boards closely upon arrival."
            )

        return ForwardLook(
            horizon_hours=48,
            events=events,
            reload_market_assessment=market_assessment
        )
