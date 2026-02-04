"""
Mock Actuals Generator — Stratum 4C: Outcome Ingestion

Generates deterministic, realistic synthetic actuals for accepted plans.
Progressive arrival: pending → partial → complete across scheduler cycles.
Never overwrites manual or imported entries.

Determinism: same (plan_id, slot) → identical outputs.
"""
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.plan_outcome import PlanPredictionSnapshot, PlanOutcome
from app.engine.economics import EconomicsEngine

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")

# Economics constants — imported from shared source, not hardcoded
_econ = EconomicsEngine()
FUEL_PER_MILE = Decimal(str(_econ.FUEL_COST_PER_MILE))
TOLL_PER_MILE = Decimal(str(_econ.TOLL_COST_PER_MILE))
MAINT_PER_MILE = Decimal(str(_econ.MAINTENANCE_RESERVE_PER_MILE))

# Actual fields on PlanOutcome that indicate data presence
ACTUAL_FIELDS = [
    "actual_revenue", "actual_fuel_spend", "actual_tolls",
    "actual_maintenance", "actual_other_costs",
    "actual_miles_loaded", "actual_miles_deadhead",
    "actual_drive_min", "actual_wait_min",
]


# ---------- Deterministic helpers ----------


def _time_slot(now: Optional[datetime] = None) -> str:
    """15-minute UTC slot string, e.g. '2026-02-01T03:45Z'."""
    if now is None:
        now = datetime.now(timezone.utc)
    # Truncate to 15-minute boundary
    minute = (now.minute // 15) * 15
    return now.strftime(f"%Y-%m-%dT%H:{minute:02d}Z")


def _variance_seed(plan_id: str, field: str, slot: str) -> int:
    """Deterministic seed from MD5 of (plan_id, field, slot)."""
    raw = f"{plan_id}-{field}-{slot}"
    return int(hashlib.md5(raw.encode()).hexdigest(), 16)


def _rand01(seed: int) -> Decimal:
    """Deterministic uniform-ish value in [0, 1) from seed."""
    return Decimal(str((seed % 10000) / 10000))


def _apply_variance(
    base: Decimal,
    plan_id: str,
    field: str,
    slot: str,
    min_factor: float,
    max_factor: float,
) -> Decimal:
    """Apply controlled variance to a base value. Returns quantized Decimal."""
    if base is None or base == 0:
        return Decimal("0.00")
    seed = _variance_seed(plan_id, field, slot)
    r = _rand01(seed)
    factor = Decimal(str(min_factor)) + r * (Decimal(str(max_factor)) - Decimal(str(min_factor)))
    return (base * factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _apply_int_variance(
    base: int,
    plan_id: str,
    field: str,
    slot: str,
    min_factor: float,
    max_factor: float,
) -> int:
    """Apply controlled variance to an integer base value."""
    if base is None or base == 0:
        return 0
    result = _apply_variance(
        Decimal(str(base)), plan_id, field, slot, min_factor, max_factor
    )
    return int(result)


# ---------- Progressive stage ----------


def _stage(plan_id: str, slot: str) -> str:
    """Determine if actuals should be 'partial' or 'complete' on first pass.
    ~40% go straight to complete; 60% partial first."""
    seed = _variance_seed(plan_id, "stage", slot)
    bucket = seed % 100
    return "complete" if bucket < 40 else "partial"


# ---------- Cost breakdown ----------


def extract_cost_breakdown(
    predicted_costs: Decimal,
    predicted_miles: Optional[int],
) -> Dict[str, Decimal]:
    """Split predicted_costs into fuel/tolls/maintenance/other using economics ratios.

    Uses shared EconomicsEngine constants — not hardcoded magic numbers.
    """
    if predicted_costs is None or predicted_costs <= 0:
        return {
            "fuel": Decimal("0.00"),
            "tolls": Decimal("0.00"),
            "maintenance": Decimal("0.00"),
            "other": Decimal("0.00"),
        }

    miles = Decimal(str(predicted_miles or 0))
    if miles <= 0:
        # Can't split by miles — use rough proportions
        return {
            "fuel": (predicted_costs * Decimal("0.60")).quantize(TWO_PLACES),
            "tolls": (predicted_costs * Decimal("0.10")).quantize(TWO_PLACES),
            "maintenance": (predicted_costs * Decimal("0.15")).quantize(TWO_PLACES),
            "other": (predicted_costs * Decimal("0.15")).quantize(TWO_PLACES),
        }

    # Cost per mile for each category
    total_per_mile = FUEL_PER_MILE + TOLL_PER_MILE + MAINT_PER_MILE
    if total_per_mile == 0:
        total_per_mile = Decimal("1.12")  # fallback

    fuel_ratio = FUEL_PER_MILE / total_per_mile
    toll_ratio = TOLL_PER_MILE / total_per_mile
    maint_ratio = MAINT_PER_MILE / total_per_mile

    fuel = (predicted_costs * fuel_ratio).quantize(TWO_PLACES)
    tolls = (predicted_costs * toll_ratio).quantize(TWO_PLACES)
    maintenance = (predicted_costs * maint_ratio).quantize(TWO_PLACES)
    other = (predicted_costs - fuel - tolls - maintenance).quantize(TWO_PLACES)
    if other < 0:
        other = Decimal("0.00")

    return {
        "fuel": fuel,
        "tolls": tolls,
        "maintenance": maintenance,
        "other": other,
    }


# ---------- Write safety ----------


def _has_any_actuals(outcome: PlanOutcome) -> bool:
    """Check if any actual_* field is already set."""
    for field in ACTUAL_FIELDS:
        if getattr(outcome, field, None) is not None:
            return True
    return False


def _should_skip(outcome: PlanOutcome) -> bool:
    """Do-not-overwrite contract:
    - source == 'manual' → always skip
    - source != 'mock_actuals' AND any actual_* exists → skip
    """
    if outcome.source == "manual":
        return True
    if outcome.source != "mock_actuals" and _has_any_actuals(outcome):
        return True
    return False


# ---------- Actuals generation ----------


def _generate_partial_actuals(
    snapshot: PlanPredictionSnapshot,
    plan_id: str,
    slot: str,
) -> Dict[str, Any]:
    """Generate partial actuals: revenue, miles, time (ELD-like data)."""
    patch: Dict[str, Any] = {}

    # Revenue ±5%
    if snapshot.predicted_revenue is not None:
        patch["actual_revenue"] = _apply_variance(
            Decimal(str(snapshot.predicted_revenue)),
            plan_id, "revenue", slot, 0.95, 1.05,
        )

    # Miles loaded ±5%
    if snapshot.predicted_miles_total is not None:
        total_pred = snapshot.predicted_miles_total
        dh_pred = snapshot.predicted_miles_deadhead or 0
        loaded_pred = total_pred - dh_pred
        patch["actual_miles_loaded"] = _apply_int_variance(
            loaded_pred, plan_id, "miles_loaded", slot, 0.95, 1.05,
        )
        # Miles deadhead ±15%
        patch["actual_miles_deadhead"] = _apply_int_variance(
            dh_pred, plan_id, "miles_deadhead", slot, 0.85, 1.15,
        )

    # Drive time +5% to +15%
    if snapshot.predicted_duration_min is not None:
        # Approximate drive vs wait split: 80% drive, 20% wait
        total = snapshot.predicted_duration_min
        drive_pred = int(total * 0.8)
        wait_pred = total - drive_pred
        patch["actual_drive_min"] = _apply_int_variance(
            drive_pred, plan_id, "drive_min", slot, 1.05, 1.15,
        )
        # Wait time +20% to +80%
        patch["actual_wait_min"] = _apply_int_variance(
            max(wait_pred, 15), plan_id, "wait_min", slot, 1.20, 1.80,
        )

    return patch


def _generate_complete_actuals(
    snapshot: PlanPredictionSnapshot,
    plan_id: str,
    slot: str,
) -> Dict[str, Any]:
    """Generate complete cost fields (accounting data)."""
    patch: Dict[str, Any] = {}

    predicted_costs = Decimal(str(snapshot.predicted_costs)) if snapshot.predicted_costs else Decimal("0")
    predicted_miles = snapshot.predicted_miles_total

    breakdown = extract_cost_breakdown(predicted_costs, predicted_miles)

    # Fuel +10% to +25%
    patch["actual_fuel_spend"] = _apply_variance(
        breakdown["fuel"], plan_id, "fuel", slot, 1.10, 1.25,
    )
    # Tolls ±15%
    patch["actual_tolls"] = _apply_variance(
        breakdown["tolls"], plan_id, "tolls", slot, 0.85, 1.15,
    )
    # Maintenance ±20%
    patch["actual_maintenance"] = _apply_variance(
        breakdown["maintenance"], plan_id, "maintenance", slot, 0.80, 1.20,
    )
    # Other costs $0-$200
    seed = _variance_seed(plan_id, "other_costs", slot)
    other_amount = Decimal(str((seed % 200))).quantize(TWO_PLACES)
    patch["actual_other_costs"] = other_amount

    # Build JSONB breakdown for audit trail
    patch["actual"] = {
        "fuel_spend": str(patch["actual_fuel_spend"]),
        "tolls": str(patch["actual_tolls"]),
        "maintenance": str(patch["actual_maintenance"]),
        "other_costs": str(patch["actual_other_costs"]),
        "source": "mock_actuals",
        "slot": slot,
    }

    return patch


def _apply_completion(outcome: PlanOutcome) -> None:
    """Apply same auto-status detection as PATCH /outcomes endpoint.
    Ensures mock outcomes obey same closure constraints as manual completion.
    """
    required_for_complete = [outcome.actual_revenue, outcome.actual_fuel_spend]
    has_any = any(
        getattr(outcome, f) is not None
        for f in ["actual_revenue", "actual_fuel_spend", "actual_tolls",
                   "actual_miles_loaded", "actual_drive_min"]
    )
    has_required = all(v is not None for v in required_for_complete)
    if has_required:
        outcome.status = "complete"
        outcome.completed_at = datetime.now(timezone.utc)
    elif has_any:
        outcome.status = "partial"


# ---------- Main loop ----------


def run_outcome_ingestion(db: Session, org_id: str) -> Dict[str, int]:
    """
    Process pending/partial outcomes for an org.
    Returns stats: {processed, partial_count, complete_count, skipped}.
    """
    slot = _time_slot()
    stats = {"processed": 0, "partial_count": 0, "complete_count": 0, "skipped": 0}

    outcomes = (
        db.query(PlanOutcome)
        .filter(
            PlanOutcome.org_id == org_id,
            PlanOutcome.status.in_(["pending", "partial"]),
        )
        .all()
    )

    for outcome in outcomes:
        # Write safety
        if _should_skip(outcome):
            stats["skipped"] += 1
            continue

        # Load linked snapshot
        snapshot = None
        if outcome.prediction_snapshot_id:
            snapshot = db.query(PlanPredictionSnapshot).get(outcome.prediction_snapshot_id)
        if not snapshot:
            snapshot = (
                db.query(PlanPredictionSnapshot)
                .filter(
                    PlanPredictionSnapshot.org_id == org_id,
                    PlanPredictionSnapshot.plan_id == outcome.plan_id,
                )
                .order_by(PlanPredictionSnapshot.created_at.desc())
                .first()
            )
        if not snapshot:
            stats["skipped"] += 1
            continue

        plan_id = outcome.plan_id

        if outcome.status == "pending":
            # First pass: generate partial or complete
            stage = _stage(plan_id, slot)

            # Always generate partial fields first
            partial_patch = _generate_partial_actuals(snapshot, plan_id, slot)
            for field, value in partial_patch.items():
                if getattr(outcome, field, None) is None:  # only fill missing
                    setattr(outcome, field, value)

            if stage == "complete":
                # Also fill cost fields on first pass
                complete_patch = _generate_complete_actuals(snapshot, plan_id, slot)
                for field, value in complete_patch.items():
                    if getattr(outcome, field, None) is None:
                        setattr(outcome, field, value)

            outcome.source = "mock_actuals"
            _apply_completion(outcome)
            stats["processed"] += 1
            if outcome.status == "complete":
                stats["complete_count"] += 1
            else:
                stats["partial_count"] += 1

        elif outcome.status == "partial" and outcome.source == "mock_actuals":
            # Second pass: fill remaining cost fields
            complete_patch = _generate_complete_actuals(snapshot, plan_id, slot)
            for field, value in complete_patch.items():
                if getattr(outcome, field, None) is None:  # only fill missing
                    setattr(outcome, field, value)

            _apply_completion(outcome)
            stats["processed"] += 1
            if outcome.status == "complete":
                stats["complete_count"] += 1
            else:
                stats["partial_count"] += 1

    return stats
