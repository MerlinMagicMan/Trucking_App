"""
Hours of Service (HOS) feasibility checker
Determines if a load can be completed within available HOS
"""
from datetime import datetime, timedelta, timezone
from typing import Tuple
from geopy.distance import geodesic

from app.models.canonical import TruckSnapshot, CanonicalLoad


# Constants
AVERAGE_SPEED_MPH = 50  # Conservative average including traffic
LOADING_TIME_HOURS = 1.5  # Time for loading at pickup
UNLOADING_TIME_HOURS = 1.5  # Time for unloading at delivery
BUFFER_TIME_HOURS = 0.5  # Safety buffer


def calculate_drive_time_minutes(distance_miles: float) -> int:
    """
    Calculate drive time in minutes based on distance
    Uses conservative average speed
    """
    hours = distance_miles / AVERAGE_SPEED_MPH
    return int(hours * 60)


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in miles between two points"""
    return geodesic((lat1, lng1), (lat2, lng2)).miles


def check_hos_feasibility(
    truck: TruckSnapshot,
    load: CanonicalLoad
) -> Tuple[bool, dict]:
    """
    Check if load is HOS-feasible for the truck

    Returns:
        Tuple of (is_feasible: bool, details: dict)

    Details dict contains:
        - deadhead_miles: Miles from truck to pickup
        - loaded_miles: Miles from pickup to delivery
        - total_miles: Total miles
        - drive_time_min: Total drive time in minutes
        - total_time_min: Total time including loading/unloading
        - arrival_at_pickup: Estimated arrival timestamp
        - arrival_at_delivery: Estimated arrival timestamp
        - hos_drive_available: Minutes available
        - hos_onduty_available: Minutes available
        - feasible_drive: Boolean
        - feasible_onduty: Boolean
        - feasible_overall: Boolean
    """
    # Calculate distances
    deadhead_miles = calculate_distance(
        truck.current_lat, truck.current_lng,
        load.pickup.lat, load.pickup.lng
    )

    loaded_miles = load.miles if load.miles else calculate_distance(
        load.pickup.lat, load.pickup.lng,
        load.delivery.lat, load.delivery.lng
    )

    total_miles = deadhead_miles + loaded_miles

    # Calculate times
    drive_time_deadhead_min = calculate_drive_time_minutes(deadhead_miles)
    drive_time_loaded_min = calculate_drive_time_minutes(loaded_miles)
    total_drive_time_min = drive_time_deadhead_min + drive_time_loaded_min

    # Total on-duty time includes driving + loading/unloading + buffer
    loading_unloading_min = int((LOADING_TIME_HOURS + UNLOADING_TIME_HOURS) * 60)
    buffer_min = int(BUFFER_TIME_HOURS * 60)
    total_onduty_time_min = total_drive_time_min + loading_unloading_min + buffer_min

    # Calculate arrival times (use timezone-aware UTC)
    now = datetime.now(timezone.utc)
    arrival_at_pickup = now + timedelta(minutes=drive_time_deadhead_min)
    arrival_at_delivery = arrival_at_pickup + timedelta(
        minutes=drive_time_loaded_min + int(LOADING_TIME_HOURS * 60)
    )

    # Check HOS constraints
    feasible_drive = total_drive_time_min <= truck.hos.drive_remaining_min
    feasible_onduty = total_onduty_time_min <= truck.hos.on_duty_remaining_min
    feasible_cycle = total_onduty_time_min <= truck.hos.cycle_remaining_min

    # Overall feasibility
    is_feasible = feasible_drive and feasible_onduty and feasible_cycle

    details = {
        "deadhead_miles": round(deadhead_miles, 1),
        "loaded_miles": round(loaded_miles, 1),
        "total_miles": round(total_miles, 1),
        "drive_time_min": total_drive_time_min,
        "total_time_min": total_onduty_time_min,
        "arrival_at_pickup": arrival_at_pickup,
        "arrival_at_delivery": arrival_at_delivery,
        "hos_drive_available": truck.hos.drive_remaining_min,
        "hos_onduty_available": truck.hos.on_duty_remaining_min,
        "hos_cycle_available": truck.hos.cycle_remaining_min,
        "feasible_drive": feasible_drive,
        "feasible_onduty": feasible_onduty,
        "feasible_cycle": feasible_cycle,
        "feasible_overall": is_feasible
    }

    return is_feasible, details


def get_infeasibility_reason(details: dict) -> str:
    """
    Generate human-readable reason for HOS infeasibility
    """
    if not details["feasible_drive"]:
        needed = details["drive_time_min"]
        available = details["hos_drive_available"]
        shortage = needed - available
        return f"Exceeds drive time by {shortage} minutes ({needed} min needed, {available} min available)"

    if not details["feasible_onduty"]:
        needed = details["total_time_min"]
        available = details["hos_onduty_available"]
        shortage = needed - available
        return f"Exceeds on-duty time by {shortage} minutes ({needed} min needed, {available} min available)"

    if not details["feasible_cycle"]:
        needed = details["total_time_min"]
        available = details["hos_cycle_available"]
        shortage = needed - available
        return f"Exceeds 70-hour cycle by {shortage} minutes"

    return "HOS feasible"
