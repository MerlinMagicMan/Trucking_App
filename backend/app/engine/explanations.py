"""
Plain-English explanation generator
Creates human-readable reasons for recommendations
"""
from typing import List
from datetime import datetime


def generate_explanations(
    deadhead_miles: float,
    loaded_miles: float,
    rate_total: float,
    arrival_at_pickup: datetime,
    arrival_at_delivery: datetime,
    pickup_window_start: datetime,
    pickup_window_end: datetime,
    delivery_window_start: datetime,
    delivery_window_end: datetime,
    delivery_city: str,
    delivery_state: str,
    is_reefer_hub: bool,
    is_strong_time_band: bool,
    reload_score: int,
    hos_details: dict
) -> List[str]:
    """
    Generate at least 3 plain-English explanations for why this load is recommended

    Prioritizes:
    1. Short deadhead
    2. Good rate/mile
    3. Reefer hub delivery
    4. Strong delivery time
    5. Comfortable pickup window
    6. HOS margin
    """
    explanations = []

    # 1. Deadhead explanation
    if deadhead_miles < 50:
        explanations.append(f"Excellent {int(deadhead_miles)}-mile deadhead to pickup")
    elif deadhead_miles < 100:
        explanations.append(f"Short {int(deadhead_miles)}-mile deadhead to pickup")
    elif deadhead_miles < 150:
        explanations.append(f"Reasonable {int(deadhead_miles)}-mile deadhead to pickup")
    else:
        explanations.append(f"{int(deadhead_miles)}-mile deadhead to pickup")

    # 2. Rate per mile
    total_miles = deadhead_miles + loaded_miles
    if total_miles > 0:
        rate_per_mile = rate_total / total_miles
        if rate_per_mile >= 2.5:
            explanations.append(f"Strong rate at ${rate_per_mile:.2f}/mile (${int(rate_total)} total)")
        elif rate_per_mile >= 2.0:
            explanations.append(f"Good rate at ${rate_per_mile:.2f}/mile (${int(rate_total)} total)")
        else:
            explanations.append(f"${rate_per_mile:.2f}/mile rate (${int(rate_total)} for {int(total_miles)} miles)")

    # 3. Delivery market & reload potential
    if is_reefer_hub:
        if is_strong_time_band:
            delivery_hour = arrival_at_delivery.hour
            time_desc = "morning" if delivery_hour < 12 else "early afternoon"
            explanations.append(
                f"Delivers into {delivery_city} reefer hub in {time_desc} - excellent reload potential"
            )
        else:
            explanations.append(f"Delivers into {delivery_city} reefer hub - good reload market")
    else:
        if is_strong_time_band:
            explanations.append(f"Delivers at good time for potential reload in {delivery_city}")
        else:
            explanations.append(f"Delivers to {delivery_city}, {delivery_state}")

    # 4. Pickup window comfort
    pickup_buffer_hours = (pickup_window_start - arrival_at_pickup).total_seconds() / 3600
    pickup_window_hours = (pickup_window_end - pickup_window_start).total_seconds() / 3600

    if pickup_buffer_hours >= 3:
        explanations.append(
            f"Comfortable {int(pickup_buffer_hours)}-hour buffer before {pickup_window_hours:.1f}-hour pickup window"
        )
    elif pickup_buffer_hours >= 1:
        explanations.append(f"{int(pickup_buffer_hours)}-hour buffer to pickup window")
    elif pickup_buffer_hours >= 0:
        explanations.append(f"Tight but achievable pickup window (arriving within window)")
    else:
        # This is risky but might still be recommended if other factors are strong
        explanations.append(f"Late pickup arrival - consider this risk")

    # 5. HOS efficiency
    drive_utilization = (hos_details["drive_time_min"] / hos_details["hos_drive_available"]) * 100
    if drive_utilization < 60:
        explanations.append(
            f"Uses only {int(drive_utilization)}% of available drive time - leaves HOS margin"
        )
    elif drive_utilization < 80:
        explanations.append(f"Efficient HOS use at {int(drive_utilization)}% of available drive time")
    else:
        explanations.append(f"Uses {int(drive_utilization)}% of available drive time")

    # 6. Distance efficiency
    if loaded_miles >= 500:
        explanations.append(f"Long haul at {int(loaded_miles)} miles maximizes revenue per trip")
    elif loaded_miles >= 300:
        explanations.append(f"Good distance at {int(loaded_miles)} miles")

    # 7. Delivery timing details
    delivery_buffer_hours = (delivery_window_start - arrival_at_delivery).total_seconds() / 3600
    if delivery_buffer_hours >= 2:
        explanations.append(f"Arrives {int(delivery_buffer_hours)} hours before delivery window - low stress")
    elif delivery_buffer_hours < 0:
        late_by_hours = abs(int(delivery_buffer_hours))
        explanations.append(f"Warning: Arrives {late_by_hours} hours after delivery window start")

    # Ensure we always return at least 3 explanations
    # If we somehow have fewer than 3, add generic positive statement
    while len(explanations) < 3:
        explanations.append(f"Reload score of {reload_score}/100 indicates reasonable opportunity")

    # Return top explanations (prioritize first ones added)
    return explanations[:5]  # Return up to 5, but minimum 3 guaranteed
