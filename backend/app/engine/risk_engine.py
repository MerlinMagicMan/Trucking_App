"""
RiskEngine - Explicit risk assessment for plans
Surfaces risks as visible RiskSignals, never hidden in black-box scoring

Risk affects explanations and confidence, NOT hidden math.
Stressed humans need to see risks clearly.
"""
from typing import List
from datetime import datetime, timedelta

from app.models.plan import RiskSignal, Plan, TimeBlock
from app.models.canonical import CanonicalLoad, TruckSnapshot
from app.engine.scoring import is_reefer_hub


class RiskEngine:
    """
    Assesses risks and creates explicit RiskSignal objects
    Every risk is visible and explained
    """

    # Risk thresholds
    HOS_TIGHT_THRESHOLD_HOURS = 3  # <3 hours drive time remaining
    TIGHT_WINDOW_THRESHOLD_HOURS = 1  # <1 hour buffer
    DEADHEAD_HIGH_THRESHOLD_MILES = 150  # >150 empty miles
    WEAK_MARKET_RELOAD_SCORE_THRESHOLD = 40  # <40 reload score

    def assess_plan_risks(self, plan: Plan) -> List[RiskSignal]:
        """
        Assess all risks for a plan

        Args:
            plan: Complete plan with timeline and loads

        Returns:
            List of RiskSignals (empty if no significant risks)
        """
        risk_signals = []

        # 1. HOS tightness risk
        hos_risks = self._assess_hos_risks(plan)
        risk_signals.extend(hos_risks)

        # 2. Appointment timing risks
        timing_risks = self._assess_timing_risks(plan)
        risk_signals.extend(timing_risks)

        # 3. Market/reload risks
        market_risks = self._assess_market_risks(plan)
        risk_signals.extend(market_risks)

        # 4. Deadhead risks
        deadhead_risks = self._assess_deadhead_risks(plan)
        risk_signals.extend(deadhead_risks)

        return risk_signals

    def _assess_hos_risks(self, plan: Plan) -> List[RiskSignal]:
        """
        Check for HOS-related risks

        Returns:
            List of HOS-related RiskSignals
        """
        risks = []
        hos = plan.truck_snapshot.hos

        # Drive time risk
        drive_hours_remaining = hos.drive_remaining_min / 60
        if drive_hours_remaining < self.HOS_TIGHT_THRESHOLD_HOURS:
            severity = "high" if drive_hours_remaining < 2 else "medium"
            impact_score = int((self.HOS_TIGHT_THRESHOLD_HOURS - drive_hours_remaining) / self.HOS_TIGHT_THRESHOLD_HOURS * 100)

            risk = RiskSignal(
                timestamp=plan.time_blocks[0].start_time if plan.time_blocks else datetime.now(),
                risk_type="hos_tight",
                severity=severity,
                description=f"Low drive time: {drive_hours_remaining:.1f} hours remaining. Consider rest break soon.",
                impact_score=min(100, max(0, impact_score))
            )
            risks.append(risk)

        # On-duty time risk
        onduty_hours_remaining = hos.on_duty_remaining_min / 60
        if onduty_hours_remaining < 4:
            severity = "high" if onduty_hours_remaining < 2 else "medium"
            impact_score = int((4 - onduty_hours_remaining) / 4 * 100)

            risk = RiskSignal(
                timestamp=plan.time_blocks[0].start_time if plan.time_blocks else datetime.now(),
                risk_type="hos_tight",
                severity=severity,
                description=f"Low on-duty time: {onduty_hours_remaining:.1f} hours remaining before 14-hour limit.",
                impact_score=min(100, max(0, impact_score))
            )
            risks.append(risk)

        return risks

    def _assess_timing_risks(self, plan: Plan) -> List[RiskSignal]:
        """
        Check for appointment timing risks

        Returns:
            List of timing-related RiskSignals
        """
        risks = []

        for load_in_plan in plan.loads:
            load = load_in_plan.load

            # Check delivery window tightness
            if load.delivery.window_start and load.delivery.window_end:
                # Find arrival time at delivery from time blocks
                arrival_time = None
                for block in load_in_plan.time_blocks:
                    if block.block_type == "drive_loaded" and block.related_load_id == load.id:
                        arrival_time = block.end_time
                        break

                if arrival_time:
                    buffer_hours = (load.delivery.window_start - arrival_time).total_seconds() / 3600

                    if buffer_hours < self.TIGHT_WINDOW_THRESHOLD_HOURS:
                        severity = "high" if buffer_hours < 0 else "medium"
                        impact_score = int((self.TIGHT_WINDOW_THRESHOLD_HOURS - buffer_hours) / self.TIGHT_WINDOW_THRESHOLD_HOURS * 80)

                        risk = RiskSignal(
                            timestamp=arrival_time,
                            risk_type="appointment_tight",
                            severity=severity,
                            description=f"Tight delivery window for {load.delivery.city}: {abs(buffer_hours):.1f} hour {'late' if buffer_hours < 0 else 'buffer'}",
                            impact_score=min(100, max(0, impact_score))
                        )
                        risks.append(risk)

            # Check pickup window tightness
            if load.pickup.window_start and load.pickup.window_end:
                # Find arrival time at pickup
                arrival_time = None
                for block in load_in_plan.time_blocks:
                    if block.block_type == "drive_empty" and block.related_load_id == load.id:
                        arrival_time = block.end_time
                        break

                if arrival_time:
                    buffer_hours = (load.pickup.window_start - arrival_time).total_seconds() / 3600

                    if buffer_hours < 0.5:  # Less than 30 min buffer
                        risk = RiskSignal(
                            timestamp=arrival_time,
                            risk_type="appointment_tight",
                            severity="medium",
                            description=f"Tight pickup window for {load.pickup.city}: {abs(buffer_hours):.1f} hour buffer",
                            impact_score=min(70, int(abs(buffer_hours - 0.5) / 0.5 * 70))
                        )
                        risks.append(risk)

        return risks

    def _assess_market_risks(self, plan: Plan) -> List[RiskSignal]:
        """
        Check for market/reload risks

        Returns:
            List of market-related RiskSignals
        """
        risks = []

        # Check final delivery location
        if plan.loads:
            final_load = plan.loads[-1]
            delivery_city = final_load.load.delivery.city
            delivery_state = final_load.load.delivery.state

            # Check if final delivery is to a known reefer hub
            is_hub, _ = is_reefer_hub(delivery_city, delivery_state)

            if not is_hub:
                # Not a reefer hub - potential weak reload market
                risk = RiskSignal(
                    timestamp=plan.time_blocks[-1].end_time if plan.time_blocks else datetime.now(),
                    risk_type="market_weak",
                    severity="low",
                    description=f"Ends in {delivery_city}, {delivery_state} - not a major reefer hub. May have fewer reload options.",
                    impact_score=30
                )
                risks.append(risk)

        return risks

    def _assess_deadhead_risks(self, plan: Plan) -> List[RiskSignal]:
        """
        Check for high deadhead risks

        Returns:
            List of deadhead-related RiskSignals
        """
        risks = []

        for load_in_plan in plan.loads:
            if load_in_plan.deadhead_miles > self.DEADHEAD_HIGH_THRESHOLD_MILES:
                severity = "high" if load_in_plan.deadhead_miles > 250 else "medium"
                impact_score = int((load_in_plan.deadhead_miles - self.DEADHEAD_HIGH_THRESHOLD_MILES) / 150 * 70)

                # Find deadhead block timestamp
                timestamp = datetime.now()
                for block in load_in_plan.time_blocks:
                    if block.block_type == "drive_empty" and block.related_load_id == load_in_plan.load.id:
                        timestamp = block.start_time
                        break

                risk = RiskSignal(
                    timestamp=timestamp,
                    risk_type="deadhead_high",
                    severity=severity,
                    description=f"High deadhead: {load_in_plan.deadhead_miles:.0f} empty miles to {load_in_plan.load.pickup.city}",
                    impact_score=min(100, max(0, impact_score))
                )
                risks.append(risk)

        return risks

    def calculate_overall_risk_level(self, risk_signals: List[RiskSignal]) -> str:
        """
        Calculate overall risk level from all signals

        Args:
            risk_signals: List of risk signals

        Returns:
            "low", "medium", or "high"
        """
        if not risk_signals:
            return "low"

        # Count by severity
        high_count = sum(1 for r in risk_signals if r.severity == "high")
        medium_count = sum(1 for r in risk_signals if r.severity == "medium")

        if high_count >= 2:
            return "high"
        elif high_count >= 1 or medium_count >= 3:
            return "medium"
        else:
            return "low"
