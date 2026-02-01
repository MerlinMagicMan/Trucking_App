"""
MockMarketConnector — simulated live market for Phase 3A

Generates ~25 deterministic but time-varying loads:
- Stable external_ids so dedup can be tested
- Loads rotate in/out based on time (simulates postings + expirations)
- Covers OK/TX/AR/LA/MO corridor for reefer
"""
import hashlib
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from app.connectors.base import BaseConnector
from app.models.canonical import CanonicalLoad, PickupDeliveryLocation
from app.analytics.geohash import encode as geohash_encode

# Fixed pool of 40 load templates; a time-varying subset is "active"
_LOAD_TEMPLATES = [
    {"ext": "MKT-001", "p_city": "Oklahoma City", "p_state": "OK", "p_lat": 35.4676, "p_lng": -97.5164, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 206, "rate": 850},
    {"ext": "MKT-002", "p_city": "Oklahoma City", "p_state": "OK", "p_lat": 35.4676, "p_lng": -97.5164, "d_city": "Houston", "d_state": "TX", "d_lat": 29.7604, "d_lng": -95.3698, "miles": 478, "rate": 1750},
    {"ext": "MKT-003", "p_city": "Oklahoma City", "p_state": "OK", "p_lat": 35.4676, "p_lng": -97.5164, "d_city": "San Antonio", "d_state": "TX", "d_lat": 29.4241, "d_lng": -98.4936, "miles": 432, "rate": 1600},
    {"ext": "MKT-004", "p_city": "Tulsa", "p_state": "OK", "p_lat": 36.1540, "p_lng": -95.9928, "d_city": "Memphis", "d_state": "TN", "d_lat": 35.1495, "d_lng": -90.0490, "miles": 401, "rate": 1480},
    {"ext": "MKT-005", "p_city": "Dallas", "p_state": "TX", "p_lat": 32.7767, "p_lng": -96.7970, "d_city": "Atlanta", "d_state": "GA", "d_lat": 33.7490, "d_lng": -84.3880, "miles": 781, "rate": 2800},
    {"ext": "MKT-006", "p_city": "Dallas", "p_state": "TX", "p_lat": 32.7767, "p_lng": -96.7970, "d_city": "New Orleans", "d_state": "LA", "d_lat": 29.9511, "d_lng": -90.0715, "miles": 504, "rate": 1850},
    {"ext": "MKT-007", "p_city": "Fort Worth", "p_state": "TX", "p_lat": 32.7555, "p_lng": -97.3308, "d_city": "Little Rock", "d_state": "AR", "d_lat": 34.7465, "d_lng": -92.2896, "miles": 318, "rate": 1200},
    {"ext": "MKT-008", "p_city": "Houston", "p_state": "TX", "p_lat": 29.7604, "p_lng": -95.3698, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 239, "rate": 920},
    {"ext": "MKT-009", "p_city": "Houston", "p_state": "TX", "p_lat": 29.7604, "p_lng": -95.3698, "d_city": "Jacksonville", "d_state": "FL", "d_lat": 30.3322, "d_lng": -81.6557, "miles": 859, "rate": 3100},
    {"ext": "MKT-010", "p_city": "San Antonio", "p_state": "TX", "p_lat": 29.4241, "p_lng": -98.4936, "d_city": "Laredo", "d_state": "TX", "d_lat": 27.5036, "d_lng": -99.5076, "miles": 157, "rate": 680},
    {"ext": "MKT-011", "p_city": "Little Rock", "p_state": "AR", "p_lat": 34.7465, "p_lng": -92.2896, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 318, "rate": 1180},
    {"ext": "MKT-012", "p_city": "Memphis", "p_state": "TN", "p_lat": 35.1495, "p_lng": -90.0490, "d_city": "Oklahoma City", "d_state": "OK", "d_lat": 35.4676, "d_lng": -97.5164, "miles": 461, "rate": 1650},
    {"ext": "MKT-013", "p_city": "Amarillo", "p_state": "TX", "p_lat": 35.2220, "p_lng": -101.8313, "d_city": "Oklahoma City", "d_state": "OK", "d_lat": 35.4676, "d_lng": -97.5164, "miles": 259, "rate": 980},
    {"ext": "MKT-014", "p_city": "Shreveport", "p_state": "LA", "p_lat": 32.5252, "p_lng": -93.7502, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 189, "rate": 780},
    {"ext": "MKT-015", "p_city": "Wichita", "p_state": "KS", "p_lat": 37.6872, "p_lng": -97.3301, "d_city": "Oklahoma City", "d_state": "OK", "d_lat": 35.4676, "d_lng": -97.5164, "miles": 161, "rate": 650},
    {"ext": "MKT-016", "p_city": "Oklahoma City", "p_state": "OK", "p_lat": 35.4676, "p_lng": -97.5164, "d_city": "Denver", "d_state": "CO", "d_lat": 39.7392, "d_lng": -104.9903, "miles": 660, "rate": 2400},
    {"ext": "MKT-017", "p_city": "Dallas", "p_state": "TX", "p_lat": 32.7767, "p_lng": -96.7970, "d_city": "Nashville", "d_state": "TN", "d_lat": 36.1627, "d_lng": -86.7816, "miles": 660, "rate": 2350},
    {"ext": "MKT-018", "p_city": "Austin", "p_state": "TX", "p_lat": 30.2672, "p_lng": -97.7431, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 195, "rate": 780},
    {"ext": "MKT-019", "p_city": "Tulsa", "p_state": "OK", "p_lat": 36.1540, "p_lng": -95.9928, "d_city": "Kansas City", "d_state": "MO", "d_lat": 39.0997, "d_lng": -94.5786, "miles": 249, "rate": 950},
    {"ext": "MKT-020", "p_city": "Oklahoma City", "p_state": "OK", "p_lat": 35.4676, "p_lng": -97.5164, "d_city": "Memphis", "d_state": "TN", "d_lat": 35.1495, "d_lng": -90.0490, "miles": 461, "rate": 1700},
    {"ext": "MKT-021", "p_city": "Dallas", "p_state": "TX", "p_lat": 32.7767, "p_lng": -96.7970, "d_city": "Chicago", "d_state": "IL", "d_lat": 41.8781, "d_lng": -87.6298, "miles": 917, "rate": 3200},
    {"ext": "MKT-022", "p_city": "Houston", "p_state": "TX", "p_lat": 29.7604, "p_lng": -95.3698, "d_city": "Laredo", "d_state": "TX", "d_lat": 27.5036, "d_lng": -99.5076, "miles": 318, "rate": 1150},
    {"ext": "MKT-023", "p_city": "El Paso", "p_state": "TX", "p_lat": 31.7619, "p_lng": -106.4850, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 571, "rate": 2050},
    {"ext": "MKT-024", "p_city": "Lubbock", "p_state": "TX", "p_lat": 33.5779, "p_lng": -101.8552, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 322, "rate": 1220},
    {"ext": "MKT-025", "p_city": "Oklahoma City", "p_state": "OK", "p_lat": 35.4676, "p_lng": -97.5164, "d_city": "Little Rock", "d_state": "AR", "d_lat": 34.7465, "d_lng": -92.2896, "miles": 344, "rate": 1280},
    {"ext": "MKT-026", "p_city": "Springfield", "p_state": "MO", "p_lat": 37.2090, "p_lng": -93.2923, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 452, "rate": 1650},
    {"ext": "MKT-027", "p_city": "Dallas", "p_state": "TX", "p_lat": 32.7767, "p_lng": -96.7970, "d_city": "Miami", "d_state": "FL", "d_lat": 25.7617, "d_lng": -80.1918, "miles": 1312, "rate": 4500},
    {"ext": "MKT-028", "p_city": "Houston", "p_state": "TX", "p_lat": 29.7604, "p_lng": -95.3698, "d_city": "Oklahoma City", "d_state": "OK", "d_lat": 35.4676, "d_lng": -97.5164, "miles": 478, "rate": 1700},
    {"ext": "MKT-029", "p_city": "Baton Rouge", "p_state": "LA", "p_lat": 30.4515, "p_lng": -91.1871, "d_city": "Dallas", "d_state": "TX", "d_lat": 32.7767, "d_lng": -96.7970, "miles": 462, "rate": 1680},
    {"ext": "MKT-030", "p_city": "Oklahoma City", "p_state": "OK", "p_lat": 35.4676, "p_lng": -97.5164, "d_city": "Austin", "d_state": "TX", "d_lat": 30.2672, "d_lng": -97.7431, "miles": 375, "rate": 1400},
]

# Total pool = 30 templates; ~20-25 active at any time


def _time_slot() -> int:
    """Return a rotating time-slot that changes every 15 minutes."""
    now = datetime.utcnow()
    return int(now.timestamp()) // (15 * 60)


def _is_active(ext_id: str, slot: int) -> bool:
    """Deterministically decide if a load is active in the current time slot."""
    h = int(hashlib.md5(f"{ext_id}-{slot}".encode()).hexdigest(), 16)
    # ~75% chance active → roughly 22-23 loads visible at any time
    return (h % 100) < 75


def _rate_jitter(base_rate: float, ext_id: str, slot: int) -> float:
    """Small deterministic rate fluctuation ±10%."""
    h = int(hashlib.md5(f"rate-{ext_id}-{slot}".encode()).hexdigest(), 16)
    factor = 0.90 + (h % 200) / 1000.0  # 0.90 – 1.10
    return round(base_rate * factor, 2)


class MockMarketConnector(BaseConnector):
    """
    Simulated live market — deterministic but time-varying loads.
    Used when no real load board API credentials exist.
    """

    def __init__(self):
        super().__init__(name="mock_market")

    def search_loads(
        self,
        truck_lat: float,
        truck_lng: float,
        radius_miles: int = 250,
        equipment: str = "reefer",
        **kwargs,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        slot = _time_slot()
        now = datetime.utcnow()
        raw_loads = []

        for tpl in _LOAD_TEMPLATES:
            if not _is_active(tpl["ext"], slot):
                continue

            rate = _rate_jitter(tpl["rate"], tpl["ext"], slot)
            raw_loads.append({
                "id": tpl["ext"],
                "posted_at": (now - timedelta(hours=2)).isoformat() + "Z",
                "equipment": "reefer",
                "pickup": {
                    "city": tpl["p_city"],
                    "state": tpl["p_state"],
                    "lat": tpl["p_lat"],
                    "lng": tpl["p_lng"],
                    "window_start": (now + timedelta(hours=6)).isoformat() + "Z",
                    "window_end": (now + timedelta(hours=18)).isoformat() + "Z",
                },
                "delivery": {
                    "city": tpl["d_city"],
                    "state": tpl["d_state"],
                    "lat": tpl["d_lat"],
                    "lng": tpl["d_lng"],
                    "window_start": (now + timedelta(hours=24)).isoformat() + "Z",
                    "window_end": (now + timedelta(hours=48)).isoformat() + "Z",
                },
                "rate_total": rate,
                "miles": tpl["miles"],
            })

        metadata = {
            "connector": self.name,
            "truck_location": {"lat": truck_lat, "lng": truck_lng},
            "radius_miles": radius_miles,
            "equipment": equipment,
            "total_loads_found": len(raw_loads),
            "query_timestamp": now.isoformat(),
            "time_slot": slot,
        }
        return raw_loads, metadata

    def normalize(self, raw_load: Dict[str, Any]) -> CanonicalLoad:
        posted_at = datetime.fromisoformat(raw_load["posted_at"].replace("Z", "+00:00"))

        def _parse_dt(d, key):
            v = d.get(key)
            if v:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            return None

        p = raw_load["pickup"]
        d = raw_load["delivery"]

        return CanonicalLoad(
            id=f"mock_market_{raw_load['id']}",
            source="mock_market",
            external_id=raw_load["id"],
            posted_at=posted_at,
            equipment="reefer",
            pickup=PickupDeliveryLocation(
                city=p["city"], state=p["state"], lat=p["lat"], lng=p["lng"],
                window_start=_parse_dt(p, "window_start"),
                window_end=_parse_dt(p, "window_end"),
            ),
            delivery=PickupDeliveryLocation(
                city=d["city"], state=d["state"], lat=d["lat"], lng=d["lng"],
                window_start=_parse_dt(d, "window_start"),
                window_end=_parse_dt(d, "window_end"),
            ),
            rate_total=raw_load["rate_total"],
            miles=raw_load.get("miles"),
            pickup_geohash=geohash_encode(p["lat"], p["lng"]),
            delivery_geohash=geohash_encode(d["lat"], d["lng"]),
        )

    def health_check(self) -> Dict[str, Any]:
        slot = _time_slot()
        active_count = sum(1 for t in _LOAD_TEMPLATES if _is_active(t["ext"], slot))
        return {
            "status": "ok",
            "connector": self.name,
            "message": f"Mock market active ({active_count} loads in current slot)",
            "loads_available": active_count,
        }
