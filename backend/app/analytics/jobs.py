"""
Analytics computation jobs — Phase 3B

All jobs derive analytics from load_snapshots.
Deterministic: same snapshot data + same window → same output.
All jobs use UPSERT so they are safe to rerun.
"""
import logging
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.snapshot import LoadSnapshot
from app.models.analytics import LaneStatistic, MarketStatistic, DestinationScore
from app.analytics.geohash import encode as geohash_encode

logger = logging.getLogger(__name__)

# Geohash precision for grouping (precision 4 ≈ ±20km)
GEOHASH_PRECISION = 4

# Minimum samples to publish lane stats
MIN_LANE_SAMPLES = 5

# Market temperature thresholds
HOT_NEW_LOADS_MIN = 20
HOT_RELOAD_DEPTH_MAX = 1.5
COLD_NEW_LOADS_MAX = 5
COLD_RELOAD_DEPTH_MIN = 3.0

# Time-to-cover gap threshold (minutes) — if load not seen for this long, treat as covered
COVER_GAP_MINUTES = 30


def compute_percentile(values: List[float], p: float) -> Optional[float]:
    """Compute p-th percentile (0-100) from sorted values. Returns None if empty."""
    if not values:
        return None
    sorted_v = sorted(values)
    n = len(sorted_v)
    k = (p / 100.0) * (n - 1)
    f = int(k)
    c = f + 1
    if c >= n:
        return round(sorted_v[-1], 2)
    d = k - f
    return round(sorted_v[f] + d * (sorted_v[c] - sorted_v[f]), 2)


def compute_market_temperature(new_loads_count: int, reload_depth: float) -> str:
    """Deterministic market temperature label."""
    if new_loads_count >= HOT_NEW_LOADS_MIN and reload_depth <= HOT_RELOAD_DEPTH_MAX:
        return "hot"
    if new_loads_count <= COLD_NEW_LOADS_MAX and reload_depth >= COLD_RELOAD_DEPTH_MIN:
        return "cold"
    return "neutral"


def compute_efficiency_score(
    reload_probability: Optional[float],
    avg_time_to_reload_min: Optional[float],
    volatility: Optional[float] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Compute destination efficiency score (0-100).
    Returns (score, explanation_dict). None if insufficient data.
    """
    if reload_probability is None:
        return None, {"reason": "insufficient_data"}

    score = 50.0
    components = {}

    # +0..30 from reload probability
    reload_bonus = reload_probability * 30.0
    score += reload_bonus
    components["reload_probability_bonus"] = round(reload_bonus, 2)

    # -0..20 from avg time to first reload
    if avg_time_to_reload_min is not None:
        # Scale: 0 min → 0 penalty, 120+ min → -20
        time_penalty = min(20.0, (avg_time_to_reload_min / 120.0) * 20.0)
        score -= time_penalty
        components["time_penalty"] = round(time_penalty, 2)

    # -0..10 from volatility
    if volatility is not None:
        vol_penalty = min(10.0, volatility * 10.0)
        score -= vol_penalty
        components["volatility_penalty"] = round(vol_penalty, 2)

    score = max(0.0, min(100.0, score))
    components["final_score"] = round(score, 2)
    return round(score, 2), components


# ---------------------------------------------------------------------------
# Lane statistics job
# ---------------------------------------------------------------------------

def compute_lane_statistics(
    db: Session,
    org_id: str,
    source: str,
    window_start: datetime,
    window_end: datetime,
) -> int:
    """
    Compute lane_statistics for all lanes visible in the window.
    Returns count of rows upserted.
    """
    snapshots = (
        db.query(LoadSnapshot)
        .filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.source == source,
            LoadSnapshot.ingested_at >= window_start,
            LoadSnapshot.ingested_at < window_end,
        )
        .all()
    )

    if not snapshots:
        return 0

    # Group by (origin_geohash, destination_geohash, equipment)
    lanes: Dict[Tuple[str, str, str], List[LoadSnapshot]] = defaultdict(list)
    for snap in snapshots:
        if snap.pickup_lat is None or snap.delivery_lat is None:
            continue
        origin_gh = geohash_encode(snap.pickup_lat, snap.pickup_lng, GEOHASH_PRECISION)
        dest_gh = geohash_encode(snap.delivery_lat, snap.delivery_lng, GEOHASH_PRECISION)
        equip = snap.equipment or "reefer"
        lanes[(origin_gh, dest_gh, equip)].append(snap)

    now = datetime.now(timezone.utc)
    count = 0

    for (origin_gh, dest_gh, equip), snaps in lanes.items():
        # Deduplicate by external_id (take latest per load identity)
        by_ext: Dict[str, List[LoadSnapshot]] = defaultdict(list)
        for s in snaps:
            by_ext[s.external_id].append(s)

        # Collect rates from unique loads
        rates = []
        miles_list = []
        cover_times = []

        for ext_id, observations in by_ext.items():
            observations.sort(key=lambda s: s.ingested_at)
            latest = observations[-1]
            if latest.rate_total is not None and latest.rate_total > 0:
                rates.append(latest.rate_total)
            if latest.miles is not None and latest.miles > 0:
                miles_list.append(latest.miles)

            # Time-to-cover: first_seen → last_seen (only if load "disappeared")
            if len(observations) >= 2:
                first_seen = observations[0].ingested_at
                last_seen = observations[-1].ingested_at
                gap = (last_seen - first_seen).total_seconds() / 60.0
                if gap > 0:
                    cover_times.append(gap)

        load_count = len(by_ext)
        if load_count < MIN_LANE_SAMPLES:
            continue

        avg_m = round(statistics.mean(miles_list), 2) if miles_list else None
        avg_rpm = None
        if rates and miles_list:
            rpms = [r / m for r, m in zip(rates, miles_list) if m > 0]
            avg_rpm = round(statistics.mean(rpms), 2) if rpms else None

        # Volatility: coefficient of variation of rates
        volatility = None
        if len(rates) >= 2:
            mean_r = statistics.mean(rates)
            if mean_r > 0:
                volatility = round(statistics.stdev(rates) / mean_r, 4)

        ttc_p50 = compute_percentile(cover_times, 50) if len(cover_times) >= 3 else None

        values = dict(
            org_id=org_id,
            source=source,
            equipment_type=equip,
            origin_geohash=origin_gh,
            destination_geohash=dest_gh,
            window_start=window_start,
            window_end=window_end,
            computed_at=now,
            load_count=load_count,
            rate_p25=compute_percentile(rates, 25),
            rate_p50=compute_percentile(rates, 50),
            rate_p75=compute_percentile(rates, 75),
            rate_p90=compute_percentile(rates, 90),
            avg_miles=avg_m,
            avg_rate_per_mile=avg_rpm,
            time_to_cover_p50_minutes=ttc_p50,
            volatility_score=volatility,
        )

        stmt = pg_insert(LaneStatistic).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_lane_stat_window",
            set_={k: v for k, v in values.items() if k not in (
                "org_id", "source", "equipment_type",
                "origin_geohash", "destination_geohash",
                "window_start", "window_end",
            )},
        )
        db.execute(stmt)
        count += 1

    return count


# ---------------------------------------------------------------------------
# Market statistics job
# ---------------------------------------------------------------------------

def compute_market_statistics(
    db: Session,
    org_id: str,
    source: str,
    window_start: datetime,
    window_end: datetime,
) -> int:
    """
    Compute market_statistics for all destination markets in the window.
    Returns count of rows upserted.
    """
    # All snapshots in window
    in_window = (
        db.query(LoadSnapshot)
        .filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.source == source,
            LoadSnapshot.ingested_at >= window_start,
            LoadSnapshot.ingested_at < window_end,
        )
        .all()
    )

    if not in_window:
        return 0

    # Group by destination geohash
    markets: Dict[str, List[LoadSnapshot]] = defaultdict(list)
    for snap in in_window:
        if snap.delivery_lat is None:
            continue
        gh = geohash_encode(snap.delivery_lat, snap.delivery_lng, GEOHASH_PRECISION)
        markets[gh].append(snap)

    now = datetime.now(timezone.utc)
    count = 0

    for market_gh, snaps in markets.items():
        # Deduplicate by external_id
        by_ext: Dict[str, List[LoadSnapshot]] = defaultdict(list)
        for s in snaps:
            by_ext[s.external_id].append(s)

        # "New" loads: first observation in window
        new_loads = 0
        expired_loads = 0
        active_counts = []  # per-observation active count estimation

        for ext_id, observations in by_ext.items():
            observations.sort(key=lambda s: s.ingested_at)
            # If first observation is near window_start, it was already existing; otherwise new
            first = observations[0]
            if (first.ingested_at - window_start).total_seconds() > COVER_GAP_MINUTES * 60:
                new_loads += 1

            # If load disappeared before window end
            last = observations[-1]
            if last.status == "expired" or (window_end - last.ingested_at).total_seconds() > COVER_GAP_MINUTES * 60:
                expired_loads += 1

        total_unique = len(by_ext)
        # Simple active average: total unique loads that had at least 1 active observation
        active_load_count_avg = float(total_unique)

        reload_depth = active_load_count_avg / max(new_loads, 1)
        temperature = compute_market_temperature(new_loads, reload_depth)

        values = dict(
            org_id=org_id,
            source=source,
            market_geohash=market_gh,
            window_start=window_start,
            window_end=window_end,
            computed_at=now,
            active_load_count_avg=active_load_count_avg,
            new_loads_count=new_loads,
            expired_loads_count=expired_loads,
            reload_depth=round(reload_depth, 4),
            market_temperature=temperature,
        )

        stmt = pg_insert(MarketStatistic).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_market_stat_window",
            set_={k: v for k, v in values.items() if k not in (
                "org_id", "source", "market_geohash", "window_start", "window_end",
            )},
        )
        db.execute(stmt)
        count += 1

    return count


# ---------------------------------------------------------------------------
# Destination scores job
# ---------------------------------------------------------------------------

def compute_destination_scores(
    db: Session,
    org_id: str,
    source: str,
    window_start: datetime,
    window_end: datetime,
) -> int:
    """
    Compute destination_scores for all delivery destinations in the window.
    Returns count of rows upserted.
    """
    snapshots = (
        db.query(LoadSnapshot)
        .filter(
            LoadSnapshot.org_id == org_id,
            LoadSnapshot.source == source,
            LoadSnapshot.ingested_at >= window_start,
            LoadSnapshot.ingested_at < window_end,
        )
        .all()
    )

    if not snapshots:
        return 0

    # Group by destination geohash
    destinations: Dict[str, List[LoadSnapshot]] = defaultdict(list)
    for snap in snapshots:
        if snap.delivery_lat is None:
            continue
        gh = geohash_encode(snap.delivery_lat, snap.delivery_lng, GEOHASH_PRECISION)
        destinations[gh].append(snap)

    # Also group by pickup geohash (to find outbound loads from each destination)
    pickup_by_gh: Dict[str, List[LoadSnapshot]] = defaultdict(list)
    for snap in snapshots:
        if snap.pickup_lat is None:
            continue
        gh = geohash_encode(snap.pickup_lat, snap.pickup_lng, GEOHASH_PRECISION)
        pickup_by_gh[gh].append(snap)

    now = datetime.now(timezone.utc)
    count = 0

    for dest_gh, delivery_snaps in destinations.items():
        # Deduplicate deliveries
        by_ext_delivery: Dict[str, List[LoadSnapshot]] = defaultdict(list)
        for s in delivery_snaps:
            by_ext_delivery[s.external_id].append(s)
        delivery_count = len(by_ext_delivery)

        # Outbound loads from this destination (loads with pickup in same geohash)
        outbound_snaps = pickup_by_gh.get(dest_gh, [])
        by_ext_outbound: Dict[str, List[LoadSnapshot]] = defaultdict(list)
        for s in outbound_snaps:
            by_ext_outbound[s.external_id].append(s)
        outbound_count = len(by_ext_outbound)

        # Reload probability: outbound_count / max(delivery_count, 1)
        reload_prob = min(1.0, outbound_count / max(delivery_count, 1))

        # Avg time to first reload: for each delivery load that "disappears",
        # find next outbound load posted after it
        reload_times = []
        for ext_id, obs in by_ext_delivery.items():
            obs.sort(key=lambda s: s.ingested_at)
            last_delivery = obs[-1].ingested_at

            # Find earliest outbound load posted after this delivery
            for out_ext, out_obs in by_ext_outbound.items():
                out_obs.sort(key=lambda s: s.ingested_at)
                first_outbound = out_obs[0].ingested_at
                if first_outbound > last_delivery:
                    gap_min = (first_outbound - last_delivery).total_seconds() / 60.0
                    reload_times.append(gap_min)
                    break

        avg_time_reload = None
        if reload_times:
            avg_time_reload = round(statistics.mean(reload_times), 2)

        # Rate volatility at this destination (from delivery rates)
        rates = [
            obs[-1].rate_total
            for obs in by_ext_delivery.values()
            if obs[-1].rate_total and obs[-1].rate_total > 0
        ]
        volatility = None
        if len(rates) >= 2:
            mean_r = statistics.mean(rates)
            if mean_r > 0:
                volatility = round(statistics.stdev(rates) / mean_r, 4)

        score, explanation = compute_efficiency_score(reload_prob, avg_time_reload, volatility)

        explanation["delivery_count"] = delivery_count
        explanation["outbound_count"] = outbound_count
        explanation["reload_probability"] = round(reload_prob, 4)
        if avg_time_reload is not None:
            explanation["avg_time_to_first_reload_minutes"] = avg_time_reload

        values = dict(
            org_id=org_id,
            source=source,
            destination_geohash=dest_gh,
            window_start=window_start,
            window_end=window_end,
            computed_at=now,
            reload_probability=round(reload_prob, 4),
            avg_time_to_first_reload_minutes=avg_time_reload,
            efficiency_score=score,
            volatility_score=volatility,
            explanation=explanation,
        )

        stmt = pg_insert(DestinationScore).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_dest_score_window",
            set_={k: v for k, v in values.items() if k not in (
                "org_id", "source", "destination_geohash", "window_start", "window_end",
            )},
        )
        db.execute(stmt)
        count += 1

    return count
