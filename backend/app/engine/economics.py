"""
Economics Engine - Full cost modeling for plans
Calculates true net profit including all costs:
- Fuel
- Tolls
- Waiting time
- Maintenance reserves
- Opportunity cost

Every financial calculation is transparent and auditable.
"""
from typing import List, Tuple
from app.models.plan import Plan, FinancialEvent, LoadInPlan, TimeBlock
from app.models.canonical import CanonicalLoad
from datetime import datetime, timedelta, timezone


class EconomicsEngine:
    """
    Calculates complete financial model for plans
    Models all costs explicitly for transparency
    """

    # Economic constants (configurable, loaded from DB or env in production)
    FUEL_COST_PER_MILE = 0.85        # $/mile (diesel ~$3.50/gal, 4.1 mpg for reefer)
    TOLL_COST_PER_MILE = 0.12        # $/mile (average for major corridors)
    WAITING_COST_PER_HOUR = 35.00    # $/hour (driver time value)
    MAINTENANCE_RESERVE_PER_MILE = 0.15  # $/mile (reserves for PM, tires, repairs)
    OPPORTUNITY_COST_PER_DAY = 500.00    # $/day (baseline earnings target)

    # States with significant toll roads
    TOLL_STATES = {"TX", "OK", "KS", "IL", "IN", "OH", "PA", "NJ", "NY", "MA", "FL"}

    def calculate_full_economics(self, plan: Plan) -> Plan:
        """
        Calculate complete financial model for a plan
        Updates plan with all FinancialEvents and net_profit

        Args:
            plan: Plan object with loads but without financial calculations

        Returns:
            Plan object with complete financial model
        """
        financial_events = []
        total_revenue = 0.0
        total_costs = 0.0

        # Process each load in the plan
        for load_in_plan in plan.loads:
            load = load_in_plan.load

            # 1. REVENUE from this load
            revenue_event = FinancialEvent(
                timestamp=load_in_plan.time_blocks[-1].end_time,  # When load completes
                event_type="revenue",
                amount_usd=load.rate_total,
                description=f"Load {load.external_id} revenue: ${load.rate_total:,.2f}",
                related_load_id=load.id,
                calculation_details={
                    "rate_total": load.rate_total,
                    "load_id": load.id,
                    "source": load.source
                }
            )
            financial_events.append(revenue_event)
            total_revenue += load.rate_total

            # 2. FUEL COST (deadhead + loaded miles)
            total_miles = load_in_plan.deadhead_miles + (load.miles or 0)
            fuel_cost = total_miles * self.FUEL_COST_PER_MILE
            fuel_event = FinancialEvent(
                timestamp=load_in_plan.time_blocks[-1].end_time,
                event_type="fuel_cost",
                amount_usd=-fuel_cost,  # Negative for cost
                description=f"Fuel for {total_miles:.0f} miles @ ${self.FUEL_COST_PER_MILE:.2f}/mi",
                related_load_id=load.id,
                calculation_details={
                    "total_miles": total_miles,
                    "deadhead_miles": load_in_plan.deadhead_miles,
                    "loaded_miles": load.miles,
                    "cost_per_mile": self.FUEL_COST_PER_MILE,
                    "formula": f"{total_miles} mi × ${self.FUEL_COST_PER_MILE}/mi = ${fuel_cost:.2f}"
                }
            )
            financial_events.append(fuel_event)
            total_costs += fuel_cost

            # 3. TOLL COST (estimated based on route)
            toll_cost = self._estimate_toll_cost(load, load_in_plan.deadhead_miles)
            if toll_cost > 0:
                toll_event = FinancialEvent(
                    timestamp=load_in_plan.time_blocks[-1].end_time,
                    event_type="toll_cost",
                    amount_usd=-toll_cost,  # Negative for cost
                    description=f"Estimated tolls for {load.pickup.state} → {load.delivery.state}",
                    related_load_id=load.id,
                    calculation_details={
                        "pickup_state": load.pickup.state,
                        "delivery_state": load.delivery.state,
                        "toll_miles_estimated": total_miles if self._crosses_toll_state(load) else 0,
                        "cost_per_mile": self.TOLL_COST_PER_MILE,
                        "formula": f"{total_miles} mi × ${self.TOLL_COST_PER_MILE}/mi = ${toll_cost:.2f}"
                    }
                )
                financial_events.append(toll_event)
                total_costs += toll_cost

            # 4. WAITING COST (time spent waiting for appointment windows)
            waiting_hours = self._calculate_waiting_time(load_in_plan)
            if waiting_hours > 0:
                waiting_cost = waiting_hours * self.WAITING_COST_PER_HOUR
                waiting_event = FinancialEvent(
                    timestamp=load_in_plan.time_blocks[0].start_time,
                    event_type="waiting_cost",
                    amount_usd=-waiting_cost,  # Negative for cost
                    description=f"Waiting time: {waiting_hours:.1f} hours @ ${self.WAITING_COST_PER_HOUR:.2f}/hr",
                    related_load_id=load.id,
                    calculation_details={
                        "waiting_hours": waiting_hours,
                        "cost_per_hour": self.WAITING_COST_PER_HOUR,
                        "formula": f"{waiting_hours:.1f} hr × ${self.WAITING_COST_PER_HOUR}/hr = ${waiting_cost:.2f}"
                    }
                )
                financial_events.append(waiting_event)
                total_costs += waiting_cost

            # 5. MAINTENANCE RESERVE (future PM, tires, repairs)
            maint_reserve = total_miles * self.MAINTENANCE_RESERVE_PER_MILE
            maint_event = FinancialEvent(
                timestamp=load_in_plan.time_blocks[-1].end_time,
                event_type="maintenance_reserve",
                amount_usd=-maint_reserve,  # Negative for cost
                description=f"Maintenance reserve for {total_miles:.0f} miles",
                related_load_id=load.id,
                calculation_details={
                    "total_miles": total_miles,
                    "reserve_per_mile": self.MAINTENANCE_RESERVE_PER_MILE,
                    "formula": f"{total_miles} mi × ${self.MAINTENANCE_RESERVE_PER_MILE}/mi = ${maint_reserve:.2f}"
                }
            )
            financial_events.append(maint_event)
            total_costs += maint_reserve

        # 6. OPPORTUNITY COST (days not working within planning horizon)
        plan_duration_days = (plan.time_blocks[-1].end_time - plan.time_blocks[0].start_time).days
        if plan_duration_days < plan.planning_horizon_days:
            idle_days = plan.planning_horizon_days - plan_duration_days
            opportunity_cost = idle_days * self.OPPORTUNITY_COST_PER_DAY
            opp_event = FinancialEvent(
                timestamp=plan.time_blocks[-1].end_time,
                event_type="opportunity_cost",
                amount_usd=-opportunity_cost,  # Negative for cost
                description=f"Opportunity cost for {idle_days} idle days",
                calculation_details={
                    "idle_days": idle_days,
                    "cost_per_day": self.OPPORTUNITY_COST_PER_DAY,
                    "planning_horizon_days": plan.planning_horizon_days,
                    "plan_duration_days": plan_duration_days,
                    "formula": f"{idle_days} days × ${self.OPPORTUNITY_COST_PER_DAY}/day = ${opportunity_cost:.2f}"
                }
            )
            financial_events.append(opp_event)
            total_costs += opportunity_cost

        # Calculate net profit and profit per day (KEY METRIC)
        net_profit = total_revenue - total_costs
        profit_per_day = net_profit / plan.planning_horizon_days

        # Update plan with financial results
        plan.total_revenue_usd = total_revenue
        plan.total_costs_usd = total_costs
        plan.net_profit_usd = net_profit
        plan.profit_per_day_usd = profit_per_day
        plan.financial_events = financial_events

        return plan

    def _estimate_toll_cost(self, load: CanonicalLoad, deadhead_miles: float) -> float:
        """
        Estimate toll costs based on route
        Simple heuristic: check if route crosses known toll states

        Args:
            load: The load being transported
            deadhead_miles: Empty miles to pickup

        Returns:
            Estimated toll cost in USD
        """
        if not self._crosses_toll_state(load):
            return 0.0

        # Estimate: use total miles if crosses toll states
        total_miles = deadhead_miles + (load.miles or 0)
        return total_miles * self.TOLL_COST_PER_MILE

    def _crosses_toll_state(self, load: CanonicalLoad) -> bool:
        """Check if route crosses known toll states"""
        return (load.pickup.state in self.TOLL_STATES or
                load.delivery.state in self.TOLL_STATES)

    def _calculate_waiting_time(self, load_in_plan: LoadInPlan) -> float:
        """
        Calculate time spent waiting (early arrival to windows)

        Args:
            load_in_plan: Load with time blocks

        Returns:
            Waiting time in hours
        """
        waiting_hours = 0.0

        # Look for "waiting" time blocks
        for block in load_in_plan.time_blocks:
            if block.block_type == "waiting":
                waiting_hours += block.duration_min / 60.0

        return waiting_hours

    def get_cost_configuration(self) -> dict:
        """
        Get current cost configuration for transparency

        Returns:
            Dict of cost constants
        """
        return {
            "fuel_cost_per_mile": self.FUEL_COST_PER_MILE,
            "toll_cost_per_mile": self.TOLL_COST_PER_MILE,
            "waiting_cost_per_hour": self.WAITING_COST_PER_HOUR,
            "maintenance_reserve_per_mile": self.MAINTENANCE_RESERVE_PER_MILE,
            "opportunity_cost_per_day": self.OPPORTUNITY_COST_PER_DAY,
            "toll_states": list(self.TOLL_STATES)
        }
