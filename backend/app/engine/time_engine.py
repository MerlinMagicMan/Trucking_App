"""
TimeEngine - Explicit time modeling for plans
Converts load sequences into complete, chronological TimeBlocks

Time is NEVER implied. Every minute is accounted for.
Waiting is first-class, not hidden.
"""
from typing import List, Tuple
from datetime import datetime, timedelta, timezone

from app.models.plan import TimeBlock, LoadInPlan
from app.models.canonical import CanonicalLoad, TruckSnapshot
from app.engine.hos_checker import check_hos_feasibility, calculate_distance


class TimeEngine:
    """
    Generates complete, gap-free timelines for plans
    Every block of time is explicitly modeled
    """

    # Constants
    LOADING_TIME_HOURS = 1.5
    UNLOADING_TIME_HOURS = 1.5
    REST_BREAK_HOURS = 10.0  # HOS-mandated rest
    AVERAGE_SPEED_MPH = 50

    def build_timeline(
        self,
        truck: TruckSnapshot,
        load_sequence: List[CanonicalLoad]
    ) -> List[TimeBlock]:
        """
        Build complete chronological timeline from load sequence

        Args:
            truck: Initial truck state
            load_sequence: Ordered list of loads (1-3 loads)

        Returns:
            Complete list of TimeBlocks (chronological, gap-free)
        """
        time_blocks = []
        current_time = datetime.now(timezone.utc)
        current_lat = truck.current_lat
        current_lng = truck.current_lng

        for load in load_sequence:
            # 1. DEADHEAD (drive empty to pickup)
            deadhead_miles = calculate_distance(
                current_lat, current_lng,
                load.pickup.lat, load.pickup.lng
            )

            if deadhead_miles > 0:
                deadhead_drive_time_hours = deadhead_miles / self.AVERAGE_SPEED_MPH
                deadhead_block = TimeBlock(
                    start_time=current_time,
                    end_time=current_time + timedelta(hours=deadhead_drive_time_hours),
                    duration_min=int(deadhead_drive_time_hours * 60),
                    block_type="drive_empty",
                    location_lat=current_lat,
                    location_lng=current_lng,
                    location_name=f"Deadhead to {load.pickup.city}, {load.pickup.state}",
                    related_load_id=load.id,
                    notes=f"{deadhead_miles:.0f} miles empty"
                )
                time_blocks.append(deadhead_block)
                current_time = deadhead_block.end_time

            # 2. WAITING (if arriving before pickup window)
            if load.pickup.window_start:
                wait_hours = (load.pickup.window_start - current_time).total_seconds() / 3600
                if wait_hours > 0.1:  # More than 6 minutes of waiting
                    wait_block = TimeBlock(
                        start_time=current_time,
                        end_time=load.pickup.window_start,
                        duration_min=int(wait_hours * 60),
                        block_type="waiting",
                        location_lat=load.pickup.lat,
                        location_lng=load.pickup.lng,
                        location_name=f"{load.pickup.city}, {load.pickup.state}",
                        related_load_id=load.id,
                        notes=f"Waiting for pickup window"
                    )
                    time_blocks.append(wait_block)
                    current_time = load.pickup.window_start

            # 3. LOADING
            loading_block = TimeBlock(
                start_time=current_time,
                end_time=current_time + timedelta(hours=self.LOADING_TIME_HOURS),
                duration_min=int(self.LOADING_TIME_HOURS * 60),
                block_type="loading",
                location_lat=load.pickup.lat,
                location_lng=load.pickup.lng,
                location_name=f"{load.pickup.city}, {load.pickup.state}",
                related_load_id=load.id,
                notes="Loading at pickup"
            )
            time_blocks.append(loading_block)
            current_time = loading_block.end_time

            # 4. LOADED DRIVE (pickup to delivery)
            loaded_miles = load.miles or calculate_distance(
                load.pickup.lat, load.pickup.lng,
                load.delivery.lat, load.delivery.lng
            )
            loaded_drive_time_hours = loaded_miles / self.AVERAGE_SPEED_MPH

            loaded_drive_block = TimeBlock(
                start_time=current_time,
                end_time=current_time + timedelta(hours=loaded_drive_time_hours),
                duration_min=int(loaded_drive_time_hours * 60),
                block_type="drive_loaded",
                location_lat=load.pickup.lat,
                location_lng=load.pickup.lng,
                location_name=f"{load.pickup.city}, {load.pickup.state} → {load.delivery.city}, {load.delivery.state}",
                related_load_id=load.id,
                notes=f"{loaded_miles:.0f} loaded miles"
            )
            time_blocks.append(loaded_drive_block)
            current_time = loaded_drive_block.end_time

            # 5. WAITING (if arriving before delivery window)
            if load.delivery.window_start:
                wait_hours = (load.delivery.window_start - current_time).total_seconds() / 3600
                if wait_hours > 0.1:  # More than 6 minutes of waiting
                    wait_block = TimeBlock(
                        start_time=current_time,
                        end_time=load.delivery.window_start,
                        duration_min=int(wait_hours * 60),
                        block_type="waiting",
                        location_lat=load.delivery.lat,
                        location_lng=load.delivery.lng,
                        location_name=f"{load.delivery.city}, {load.delivery.state}",
                        related_load_id=load.id,
                        notes="Waiting for delivery window"
                    )
                    time_blocks.append(wait_block)
                    current_time = load.delivery.window_start

            # 6. UNLOADING
            unloading_block = TimeBlock(
                start_time=current_time,
                end_time=current_time + timedelta(hours=self.UNLOADING_TIME_HOURS),
                duration_min=int(self.UNLOADING_TIME_HOURS * 60),
                block_type="unloading",
                location_lat=load.delivery.lat,
                location_lng=load.delivery.lng,
                location_name=f"{load.delivery.city}, {load.delivery.state}",
                related_load_id=load.id,
                notes="Unloading at delivery"
            )
            time_blocks.append(unloading_block)
            current_time = unloading_block.end_time

            # 7. REST BREAK (mandatory 10-hour rest after each load)
            rest_block = TimeBlock(
                start_time=current_time,
                end_time=current_time + timedelta(hours=self.REST_BREAK_HOURS),
                duration_min=int(self.REST_BREAK_HOURS * 60),
                block_type="rest_break",
                location_lat=load.delivery.lat,
                location_lng=load.delivery.lng,
                location_name=f"{load.delivery.city}, {load.delivery.state}",
                related_load_id=load.id,
                notes="HOS-mandated rest (10 hours)"
            )
            time_blocks.append(rest_block)
            current_time = rest_block.end_time

            # Update position for next load
            current_lat = load.delivery.lat
            current_lng = load.delivery.lng

        # 8. AVAILABLE (after all loads complete)
        available_block = TimeBlock(
            start_time=current_time,
            end_time=current_time,  # Open-ended
            duration_min=0,
            block_type="available",
            location_lat=current_lat,
            location_lng=current_lng,
            location_name="Available for next load",
            notes="Plan complete, ready for reload"
        )
        time_blocks.append(available_block)

        return time_blocks

    def calculate_total_duration_days(self, time_blocks: List[TimeBlock]) -> int:
        """
        Calculate total plan duration in days

        Args:
            time_blocks: Complete timeline

        Returns:
            Duration in days (rounded up)
        """
        if not time_blocks:
            return 0

        start = time_blocks[0].start_time
        # Find last block that's not "available" (open-ended)
        end = time_blocks[-2].end_time if len(time_blocks) > 1 else time_blocks[-1].end_time

        duration = (end - start).total_seconds() / (24 * 3600)
        return max(1, int(duration) + (1 if duration % 1 > 0 else 0))  # Round up

    def validate_timeline(self, time_blocks: List[TimeBlock]) -> Tuple[bool, str]:
        """
        Validate timeline is chronological and gap-free

        Args:
            time_blocks: Timeline to validate

        Returns:
            (is_valid, error_message)
        """
        if not time_blocks:
            return False, "Timeline is empty"

        for i in range(len(time_blocks) - 1):
            current = time_blocks[i]
            next_block = time_blocks[i + 1]

            # Check chronological order
            if current.end_time > next_block.start_time:
                return False, f"Blocks overlap: {current.block_type} ends after {next_block.block_type} starts"

            # Check for gaps (except for open-ended "available" block)
            if next_block.block_type != "available":
                gap = (next_block.start_time - current.end_time).total_seconds()
                if gap > 60:  # More than 1 minute gap
                    return False, f"Gap of {gap/60:.1f} minutes between {current.block_type} and {next_block.block_type}"

            # Check duration matches
            expected_duration = (current.end_time - current.start_time).total_seconds() / 60
            if abs(expected_duration - current.duration_min) > 1:  # Allow 1 minute tolerance
                return False, f"Duration mismatch in {current.block_type}: expected {expected_duration:.0f}, got {current.duration_min}"

        return True, "Timeline is valid"
