"""
PlanExplanations - Plain-English narratives for plans
If a plan cannot explain itself, it is invalid.

Explanations prioritize:
1. Financial outcome (profit per day)
2. Strategic positioning (where you end up)
3. Risk profile (what could go wrong)
4. Time efficiency (HOS utilization)
"""
from typing import List

from app.models.plan import Plan
from app.engine.scoring import is_reefer_hub


def generate_plan_explanations(plan: Plan) -> List[str]:
    """
    Generate at least 3 plain-English explanations for why this plan is recommended

    Args:
        plan: Complete plan with financial model and timeline

    Returns:
        List of explanations (minimum 3, typically 4-6)
    """
    explanations = []

    # 1. FINANCIAL SUMMARY (always first)
    explanations.append(_explain_financial_outcome(plan))

    # 2. STRATEGIC POSITIONING
    explanations.append(_explain_strategic_position(plan))

    # 3. LOAD SEQUENCE
    explanations.append(_explain_load_sequence(plan))

    # 4. RISK PROFILE (if significant risks exist)
    risk_explanation = _explain_risk_profile(plan)
    if risk_explanation:
        explanations.append(risk_explanation)

    # 5. TIME EFFICIENCY
    time_explanation = _explain_time_efficiency(plan)
    if time_explanation:
        explanations.append(time_explanation)

    # 6. MARKET ASSESSMENT (if ending in notable market)
    market_explanation = _explain_market_position(plan)
    if market_explanation:
        explanations.append(market_explanation)

    # Ensure minimum 3 explanations
    if len(explanations) < 3:
        explanations.append(f"Plan covers {plan.planning_horizon_days} days with {len(plan.loads)} chained loads.")

    return explanations


def _explain_financial_outcome(plan: Plan) -> str:
    """Explain the financial result"""
    profit_per_day = plan.profit_per_day_usd
    net_profit = plan.net_profit_usd
    days = plan.planning_horizon_days

    if profit_per_day > 400:
        quality = "Excellent"
    elif profit_per_day > 300:
        quality = "Strong"
    elif profit_per_day > 200:
        quality = "Good"
    else:
        quality = "Acceptable"

    return (
        f"{quality} financial outcome: ${net_profit:,.0f} net profit over {days} days "
        f"(${profit_per_day:,.0f}/day)."
    )


def _explain_strategic_position(plan: Plan) -> str:
    """Explain where the plan ends and why that matters"""
    if not plan.loads:
        return "Strategic positioning unclear."

    final_load = plan.loads[-1]
    delivery_city = final_load.load.delivery.city
    delivery_state = final_load.load.delivery.state

    is_hub, hub_bonus = is_reefer_hub(delivery_city, delivery_state)

    if is_hub:
        return f"Ends in {delivery_city} reefer hub - excellent position for next load."
    else:
        return f"Ends in {delivery_city}, {delivery_state} - plan for next move from there."


def _explain_load_sequence(plan: Plan) -> str:
    """Explain the load chain strategy"""
    num_loads = len(plan.loads)

    if num_loads == 1:
        load = plan.loads[0].load
        return f"Single-load plan: {load.pickup.city} → {load.delivery.city} ({load.miles or 0:.0f} miles)."

    # Multi-load chain
    origins = [load.load.pickup.city for load in plan.loads]
    destinations = [load.load.delivery.city for load in plan.loads]

    # Calculate total loaded miles
    total_loaded_miles = sum(load.load.miles or 0 for load in plan.loads)

    chain_description = " → ".join(destinations)

    return f"Chains {num_loads} loads through {chain_description} ({total_loaded_miles:.0f} total loaded miles)."


def _explain_risk_profile(plan: Plan) -> str:
    """Explain risk level if significant"""
    if not plan.risk_signals:
        return None  # No significant risks

    high_risks = [r for r in plan.risk_signals if r.severity == "high"]
    medium_risks = [r for r in plan.risk_signals if r.severity == "medium"]

    if high_risks:
        risk_types = ", ".join(set(r.risk_type for r in high_risks))
        return f"⚠️ High risk: {risk_types}. Review carefully before accepting."
    elif len(medium_risks) >= 2:
        return f"Moderate risk with {len(medium_risks)} timing or market considerations."
    else:
        return None  # Low risk, don't mention


def _explain_time_efficiency(plan: Plan) -> str:
    """Explain how efficiently time is used"""
    # Calculate actual working time vs total time
    working_blocks = [b for b in plan.time_blocks if b.block_type in ["drive_empty", "drive_loaded", "loading", "unloading"]]
    waiting_blocks = [b for b in plan.time_blocks if b.block_type == "waiting"]

    working_hours = sum(b.duration_min for b in working_blocks) / 60
    waiting_hours = sum(b.duration_min for b in waiting_blocks) / 60

    if waiting_hours < 2:
        return f"Efficient timeline with minimal waiting ({working_hours:.0f} hours productive time)."
    elif waiting_hours < 5:
        return f"Timeline includes {waiting_hours:.1f} hours waiting for appointment windows."
    else:
        return f"⚠️ Significant wait time: {waiting_hours:.0f} hours waiting (consider if acceptable)."


def _explain_market_position(plan: Plan) -> str:
    """Explain market assessment at end of plan"""
    if not plan.loads:
        return None

    final_load = plan.loads[-1]
    delivery_city = final_load.load.delivery.city
    delivery_state = final_load.load.delivery.state

    # Check if it's a strong reefer market
    is_hub, hub_bonus = is_reefer_hub(delivery_city, delivery_state)

    if is_hub and hub_bonus >= 8:  # Primary hub
        # Check delivery timing
        final_delivery_time = None
        for block in plan.time_blocks:
            if block.block_type == "unloading" and block.related_load_id == final_load.load.id:
                final_delivery_time = block.start_time
                break

        if final_delivery_time:
            hour = final_delivery_time.hour
            if 6 <= hour < 10:
                return f"Delivers into {delivery_city} hub in morning - prime time for same-day reload."
            elif 10 <= hour < 14:
                return f"Delivers into {delivery_city} hub midday - good reload timing."

    return None  # No notable market insight
