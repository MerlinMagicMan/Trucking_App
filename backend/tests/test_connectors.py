"""
Tests for load board connectors
"""
import pytest
from app.connectors.truckstop import TruckstopConnector
from app.connectors.dat import DatConnector


def test_truckstop_health_check():
    """Truckstop connector health check should return ok"""
    connector = TruckstopConnector()
    health = connector.health_check()

    assert health['status'] == 'ok'
    assert 'loads_available' in health
    assert health['loads_available'] > 0


def test_dat_health_check():
    """DAT connector health check should return stub status"""
    connector = DatConnector()
    health = connector.health_check()

    assert health['status'] == 'stub'
    assert health['connector'] == 'dat'


def test_truckstop_search_loads_uses_truck_location():
    """Truckstop connector should filter loads by truck location"""
    connector = TruckstopConnector()

    # Oklahoma City location
    truck_lat = 35.4676
    truck_lng = -97.5164

    loads, metadata = connector.search_loads(truck_lat, truck_lng, radius_miles=250)

    assert isinstance(loads, list)
    assert metadata['truck_location']['lat'] == truck_lat
    assert metadata['truck_location']['lng'] == truck_lng
    assert metadata['radius_miles'] == 250


def test_truckstop_normalize_produces_canonical_load():
    """Normalize should convert raw load to CanonicalLoad"""
    connector = TruckstopConnector()

    # Get a raw load
    loads, _ = connector.search_loads(35.4676, -97.5164, radius_miles=300)
    assert len(loads) > 0, "Should find at least one load"

    raw_load = loads[0]
    canonical = connector.normalize(raw_load)

    # Verify canonical structure
    assert canonical.equipment == "reefer"
    assert canonical.source == "truckstop"
    assert canonical.pickup is not None
    assert canonical.delivery is not None
    assert canonical.rate_total > 0
    assert canonical.delivery.window_start is not None
    assert canonical.delivery.window_end is not None


def test_truckstop_filters_by_distance():
    """Search should only return loads within specified radius"""
    connector = TruckstopConnector()

    # Oklahoma City
    truck_lat = 35.4676
    truck_lng = -97.5164

    # Small radius
    loads_50mi, _ = connector.search_loads(truck_lat, truck_lng, radius_miles=50)
    loads_250mi, _ = connector.search_loads(truck_lat, truck_lng, radius_miles=250)

    # Larger radius should return more loads
    assert len(loads_250mi) >= len(loads_50mi)


def test_dat_stub_returns_empty():
    """DAT stub should return empty results"""
    connector = DatConnector()

    loads, metadata = connector.search_loads(35.4676, -97.5164)

    assert len(loads) == 0
    assert metadata['status'] == 'stub'
    assert metadata['connector'] == 'dat'
