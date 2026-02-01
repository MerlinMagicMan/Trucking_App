"""
Tests for Phase 3C: Intelligence APIs

Unit tests for time windows, negotiation math, null handling.
Integration tests skip if no PG.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.intel.time_windows import resolve_window, floor_to_hour
from app.intel.negotiation import compute_negotiation, _estimate_percentile_position


class TestTimeWindows:
    def test_floor_to_hour(self):
        dt = datetime(2025, 6, 15, 14, 37, 22, tzinfo=timezone.utc)
        floored = floor_to_hour(dt)
        assert floored == datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)

    def test_floor_exact_hour(self):
        dt = datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        assert floor_to_hour(dt) == dt

    def test_resolve_6h_default(self):
        ws, we, label = resolve_window("6h")
        assert label == "6h"
        assert we - ws == timedelta(hours=6)
        assert we.minute == 0
        assert we.second == 0

    def test_resolve_1h(self):
        ws, we, label = resolve_window("1h")
        assert we - ws == timedelta(hours=1)

    def test_resolve_24h(self):
        ws, we, label = resolve_window("24h")
        assert we - ws == timedelta(hours=24)

    def test_resolve_with_as_of(self):
        ws, we, _ = resolve_window("6h", as_of="2025-06-15T14:37:00")
        assert we == datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        assert ws == datetime(2025, 6, 15, 8, 0, 0, tzinfo=timezone.utc)

    def test_resolve_with_as_of_tz(self):
        ws, we, _ = resolve_window("1h", as_of="2025-06-15T14:37:00+00:00")
        assert we == datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)

    def test_invalid_window(self):
        with pytest.raises(ValueError, match="Invalid window"):
            resolve_window("3h")

    def test_deterministic(self):
        """Same as_of → same window."""
        w1 = resolve_window("6h", as_of="2025-01-01T12:00:00")
        w2 = resolve_window("6h", as_of="2025-01-01T12:00:00")
        assert w1 == w2


class TestNegotiation:
    def test_insufficient_data(self):
        result = compute_negotiation(
            offered_rate_usd=1000,
            rate_p25=None, rate_p50=None, rate_p75=None, rate_p90=None,
            time_to_cover_p50_minutes=None, load_count=2,
        )
        assert result["position"] is None
        assert "Insufficient" in result["explanations"][0]

    def test_below_median(self):
        result = compute_negotiation(
            offered_rate_usd=700,
            rate_p25=600, rate_p50=800, rate_p75=1000, rate_p90=1200,
            time_to_cover_p50_minutes=60, load_count=20,
        )
        assert result["position"] == "below_median"
        assert result["suggested_counter"] == 1000
        assert result["walk_away"] == 600

    def test_near_median(self):
        result = compute_negotiation(
            offered_rate_usd=850,
            rate_p25=600, rate_p50=800, rate_p75=1000, rate_p90=1200,
            time_to_cover_p50_minutes=None, load_count=10,
        )
        assert result["position"] == "near_median"

    def test_strong(self):
        result = compute_negotiation(
            offered_rate_usd=1100,
            rate_p25=600, rate_p50=800, rate_p75=1000, rate_p90=1200,
            time_to_cover_p50_minutes=None, load_count=10,
        )
        assert result["position"] == "strong"

    def test_fast_cover_explanation(self):
        result = compute_negotiation(
            offered_rate_usd=700,
            rate_p25=600, rate_p50=800, rate_p75=1000, rate_p90=1200,
            time_to_cover_p50_minutes=30, load_count=15,
        )
        assert any("covering quickly" in e for e in result["explanations"])

    def test_slow_cover_explanation(self):
        result = compute_negotiation(
            offered_rate_usd=700,
            rate_p25=600, rate_p50=800, rate_p75=1000, rate_p90=1200,
            time_to_cover_p50_minutes=240, load_count=15,
        )
        assert any("sit for a while" in e for e in result["explanations"])

    def test_deterministic(self):
        args = dict(
            offered_rate_usd=850,
            rate_p25=600, rate_p50=800, rate_p75=1000, rate_p90=1200,
            time_to_cover_p50_minutes=60, load_count=20,
        )
        r1 = compute_negotiation(**args)
        r2 = compute_negotiation(**args)
        assert r1 == r2


class TestPercentilePosition:
    def test_at_p50(self):
        pos = _estimate_percentile_position(800, 600, 800, 1000, 1200)
        assert pos == pytest.approx(50, abs=1)

    def test_at_p75(self):
        pos = _estimate_percentile_position(1000, 600, 800, 1000, 1200)
        assert pos == pytest.approx(75, abs=1)

    def test_below_p25(self):
        pos = _estimate_percentile_position(300, 600, 800, 1000, 1200)
        assert pos < 25

    def test_above_p90(self):
        pos = _estimate_percentile_position(1500, 600, 800, 1000, 1200)
        assert pos > 90

    def test_interpolation(self):
        pos = _estimate_percentile_position(900, 600, 800, 1000, 1200)
        assert 50 < pos < 75

    def test_no_markers(self):
        pos = _estimate_percentile_position(1000, None, None, None, None)
        assert pos == 50.0


class TestNullHandling:
    """Verify graceful handling when analytics tables are empty."""

    def test_negotiation_with_all_none(self):
        result = compute_negotiation(
            offered_rate_usd=1000,
            rate_p25=None, rate_p50=None, rate_p75=None, rate_p90=None,
            time_to_cover_p50_minutes=None, load_count=0,
        )
        assert result["position"] is None
        assert result["suggested_counter"] is None
        assert len(result["explanations"]) >= 1

    def test_negotiation_partial_percentiles(self):
        """p50 exists but p25/p75/p90 are None."""
        result = compute_negotiation(
            offered_rate_usd=1000,
            rate_p25=None, rate_p50=900, rate_p75=None, rate_p90=None,
            time_to_cover_p50_minutes=None, load_count=10,
        )
        assert result["position"] == "strong"  # 1000 > 900 p50, and no p75 → treat as strong
        assert result["suggested_accept"] == 900


class TestIntelAPIIntegration:
    """Integration tests — require PostgreSQL, skip otherwise."""

    @pytest.fixture
    def client(self):
        try:
            from app.db.connection import engine, Base
            Base.metadata.create_all(bind=engine)
            from fastapi.testclient import TestClient
            from app.main import app
            return TestClient(app)
        except Exception:
            pytest.skip("Database not available")

    def test_lane_endpoint_no_data(self, client):
        resp = client.get(
            "/api/intel/lane",
            params={"origin_geohash": "9y69", "destination_geohash": "9vg4", "window": "1h"},
            headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] is None
        assert body["meta"]["window"] == "1h"
        assert len(body["explanations"]) > 0

    def test_market_endpoint_no_data(self, client):
        resp = client.get(
            "/api/intel/market",
            params={"market_geohash": "9vg4", "window": "6h"},
            headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_destination_endpoint_no_data(self, client):
        resp = client.get(
            "/api/intel/destination",
            params={"destination_geohash": "9vg4"},
            headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_negotiation_endpoint_no_data(self, client):
        resp = client.get(
            "/api/intel/negotiation",
            params={
                "origin_geohash": "9y69",
                "destination_geohash": "9vg4",
                "offered_rate_usd": 1000,
            },
            headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] is None
        assert "Insufficient" in body["explanations"][0]

    def test_corridor_endpoint_no_data(self, client):
        resp = client.get(
            "/api/intel/corridor",
            params={"origin_geohash": "9y69"},
            headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_health_endpoint(self, client):
        resp = client.get(
            "/api/intel/health",
            headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["tables"]) == 3

    def test_missing_org_header(self, client):
        resp = client.get(
            "/api/intel/lane",
            params={"origin_geohash": "9y69", "destination_geohash": "9vg4"},
        )
        assert resp.status_code == 400

    def test_as_of_replay(self, client):
        resp = client.get(
            "/api/intel/lane",
            params={
                "origin_geohash": "9y69",
                "destination_geohash": "9vg4",
                "as_of": "2025-01-15T12:00:00",
            },
            headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"},
        )
        assert resp.status_code == 200
        meta = resp.json()["meta"]
        assert meta["window_end"] == "2025-01-15T12:00:00+00:00"
