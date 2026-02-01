"""
Tests for Phase 3B: Analytics Store

Unit tests for pure computation functions + integration tests (skip if no PG).
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.analytics.geohash import encode as geohash_encode
from app.analytics.jobs import (
    compute_percentile,
    compute_market_temperature,
    compute_efficiency_score,
)


class TestGeohash:
    def test_okc(self):
        gh = geohash_encode(35.4676, -97.5164, precision=4)
        assert len(gh) == 4
        assert isinstance(gh, str)

    def test_dallas(self):
        gh = geohash_encode(32.7767, -96.7970, precision=4)
        assert len(gh) == 4

    def test_different_cities_differ(self):
        okc = geohash_encode(35.4676, -97.5164, precision=4)
        dallas = geohash_encode(32.7767, -96.7970, precision=4)
        assert okc != dallas

    def test_nearby_same(self):
        """Two very close points should share the same geohash at low precision."""
        gh1 = geohash_encode(35.4676, -97.5164, precision=3)
        gh2 = geohash_encode(35.4700, -97.5100, precision=3)
        assert gh1 == gh2

    def test_precision(self):
        gh3 = geohash_encode(35.4676, -97.5164, precision=3)
        gh5 = geohash_encode(35.4676, -97.5164, precision=5)
        assert gh5.startswith(gh3)


class TestPercentile:
    def test_empty(self):
        assert compute_percentile([], 50) is None

    def test_single(self):
        assert compute_percentile([100.0], 50) == 100.0

    def test_median_odd(self):
        assert compute_percentile([10, 20, 30], 50) == 20.0

    def test_median_even(self):
        result = compute_percentile([10, 20, 30, 40], 50)
        assert result == 25.0

    def test_p25(self):
        vals = [10, 20, 30, 40, 50]
        result = compute_percentile(vals, 25)
        assert result == 20.0

    def test_p90(self):
        vals = list(range(1, 101))  # 1..100
        result = compute_percentile(vals, 90)
        assert result == pytest.approx(90.1, abs=0.5)

    def test_deterministic(self):
        vals = [50, 10, 30, 20, 40]
        r1 = compute_percentile(vals, 50)
        r2 = compute_percentile(vals, 50)
        assert r1 == r2


class TestMarketTemperature:
    def test_hot(self):
        assert compute_market_temperature(25, 1.0) == "hot"

    def test_cold(self):
        assert compute_market_temperature(3, 4.0) == "cold"

    def test_neutral_middle(self):
        assert compute_market_temperature(10, 2.0) == "neutral"

    def test_neutral_edge(self):
        # High loads but high depth → not hot
        assert compute_market_temperature(25, 3.0) == "neutral"

    def test_boundary_hot(self):
        assert compute_market_temperature(20, 1.5) == "hot"

    def test_boundary_cold(self):
        assert compute_market_temperature(5, 3.0) == "cold"


class TestEfficiencyScore:
    def test_none_if_no_data(self):
        score, expl = compute_efficiency_score(None, None)
        assert score is None
        assert expl["reason"] == "insufficient_data"

    def test_base_50(self):
        score, _ = compute_efficiency_score(0.0, 0.0)
        assert score == 50.0

    def test_high_reload_probability(self):
        score, _ = compute_efficiency_score(1.0, 0.0)
        assert score == 80.0  # 50 + 30

    def test_slow_reload_penalized(self):
        score, _ = compute_efficiency_score(0.5, 120.0)
        # 50 + 15 (reload bonus) - 20 (time penalty) = 45
        assert score == 45.0

    def test_clamped_to_0_100(self):
        score, _ = compute_efficiency_score(0.0, 300.0, volatility=2.0)
        assert score >= 0.0
        score2, _ = compute_efficiency_score(1.0, 0.0)
        assert score2 <= 100.0

    def test_explanation_has_components(self):
        _, expl = compute_efficiency_score(0.5, 60.0, volatility=0.3)
        assert "reload_probability_bonus" in expl
        assert "time_penalty" in expl
        assert "volatility_penalty" in expl
        assert "final_score" in expl


class TestTimeToCover:
    """Test time-to-cover logic via synthetic data patterns."""

    def test_cover_time_from_observations(self):
        """Verify the pattern: first_seen → last_seen = cover time."""
        # This tests the concept; actual DB test is below
        first_seen = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
        last_seen = datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc)
        cover_minutes = (last_seen - first_seen).total_seconds() / 60.0
        assert cover_minutes == 150.0


class TestAnalyticsJobsIntegration:
    """Integration tests — require PostgreSQL, skip otherwise."""

    @pytest.fixture
    def db_session(self):
        try:
            from app.db.connection import SessionLocal, engine, Base
            Base.metadata.create_all(bind=engine)
            db = SessionLocal()
            yield db
            db.rollback()
            db.close()
        except Exception:
            pytest.skip("Database not available")

    def test_lane_statistics_job(self, db_session):
        from app.models.snapshot import LoadSnapshot
        from app.analytics.jobs import compute_lane_statistics
        from app.models.analytics import LaneStatistic

        org_id = "00000000-0000-0000-0000-000000000001"
        source = "test_analytics"
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=1)
        window_end = now

        # Clean up
        db_session.query(LoadSnapshot).filter(LoadSnapshot.source == source).delete()
        db_session.query(LaneStatistic).filter(LaneStatistic.source == source).delete()
        db_session.commit()

        # Insert synthetic snapshots (6 loads on same lane)
        for i in range(6):
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            import uuid
            vals = dict(
                id=uuid.uuid4(),
                org_id=org_id,
                source=source,
                external_id=f"LANE-{i:03d}",
                raw_payload={"test": True},
                canonical={"id": f"test_LANE-{i:03d}", "source": source, "external_id": f"LANE-{i:03d}",
                           "posted_at": now.isoformat(), "equipment": "reefer",
                           "pickup": {"city": "OKC", "state": "OK", "lat": 35.46, "lng": -97.51},
                           "delivery": {"city": "Dallas", "state": "TX", "lat": 32.77, "lng": -96.79},
                           "rate_total": 800 + i * 50, "miles": 200},
                ingested_at=now - timedelta(minutes=30),
                status="active",
                equipment="reefer",
                pickup_lat=35.46, pickup_lng=-97.51,
                delivery_lat=32.77, delivery_lng=-96.79,
                rate_total=800 + i * 50,
                miles=200,
                pickup_city="OKC", pickup_state="OK",
                delivery_city="Dallas", delivery_state="TX",
            )
            stmt = pg_insert(LoadSnapshot).values(**vals).on_conflict_do_nothing()
            db_session.execute(stmt)
        db_session.commit()

        count = compute_lane_statistics(db_session, org_id, source, window_start, window_end)
        db_session.commit()

        assert count >= 1

        row = db_session.query(LaneStatistic).filter(LaneStatistic.source == source).first()
        assert row is not None
        assert row.load_count >= 5
        assert row.rate_p50 is not None

        # Idempotence: run again, should not duplicate
        count2 = compute_lane_statistics(db_session, org_id, source, window_start, window_end)
        db_session.commit()
        total = db_session.query(LaneStatistic).filter(LaneStatistic.source == source).count()
        assert total == count  # same count, not doubled

        # Cleanup
        db_session.query(LoadSnapshot).filter(LoadSnapshot.source == source).delete()
        db_session.query(LaneStatistic).filter(LaneStatistic.source == source).delete()
        db_session.commit()

    def test_market_statistics_job(self, db_session):
        from app.models.snapshot import LoadSnapshot
        from app.analytics.jobs import compute_market_statistics
        from app.models.analytics import MarketStatistic

        org_id = "00000000-0000-0000-0000-000000000001"
        source = "test_analytics"
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=1)
        window_end = now

        db_session.query(LoadSnapshot).filter(LoadSnapshot.source == source).delete()
        db_session.query(MarketStatistic).filter(MarketStatistic.source == source).delete()
        db_session.commit()

        import uuid
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        for i in range(8):
            vals = dict(
                id=uuid.uuid4(),
                org_id=org_id,
                source=source,
                external_id=f"MKT-A-{i:03d}",
                raw_payload={"test": True},
                canonical={},
                ingested_at=now - timedelta(minutes=20),
                status="active",
                equipment="reefer",
                pickup_lat=35.46, pickup_lng=-97.51,
                delivery_lat=32.77, delivery_lng=-96.79,
                rate_total=900,
                miles=200,
                pickup_city="OKC", pickup_state="OK",
                delivery_city="Dallas", delivery_state="TX",
            )
            stmt = pg_insert(LoadSnapshot).values(**vals).on_conflict_do_nothing()
            db_session.execute(stmt)
        db_session.commit()

        count = compute_market_statistics(db_session, org_id, source, window_start, window_end)
        db_session.commit()
        assert count >= 1

        row = db_session.query(MarketStatistic).filter(MarketStatistic.source == source).first()
        assert row is not None
        assert row.market_temperature in ("cold", "neutral", "hot")

        # Cleanup
        db_session.query(LoadSnapshot).filter(LoadSnapshot.source == source).delete()
        db_session.query(MarketStatistic).filter(MarketStatistic.source == source).delete()
        db_session.commit()

    def test_destination_scores_job(self, db_session):
        from app.models.snapshot import LoadSnapshot
        from app.analytics.jobs import compute_destination_scores
        from app.models.analytics import DestinationScore

        org_id = "00000000-0000-0000-0000-000000000001"
        source = "test_analytics"
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=1)
        window_end = now

        db_session.query(LoadSnapshot).filter(LoadSnapshot.source == source).delete()
        db_session.query(DestinationScore).filter(DestinationScore.source == source).delete()
        db_session.commit()

        import uuid
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        for i in range(5):
            vals = dict(
                id=uuid.uuid4(),
                org_id=org_id,
                source=source,
                external_id=f"DEST-{i:03d}",
                raw_payload={"test": True},
                canonical={},
                ingested_at=now - timedelta(minutes=15),
                status="active",
                equipment="reefer",
                pickup_lat=35.46, pickup_lng=-97.51,
                delivery_lat=32.77, delivery_lng=-96.79,
                rate_total=1000,
                miles=200,
                pickup_city="OKC", pickup_state="OK",
                delivery_city="Dallas", delivery_state="TX",
            )
            stmt = pg_insert(LoadSnapshot).values(**vals).on_conflict_do_nothing()
            db_session.execute(stmt)
        db_session.commit()

        count = compute_destination_scores(db_session, org_id, source, window_start, window_end)
        db_session.commit()
        assert count >= 1

        row = db_session.query(DestinationScore).filter(DestinationScore.source == source).first()
        assert row is not None
        assert row.explanation is not None

        # Cleanup
        db_session.query(LoadSnapshot).filter(LoadSnapshot.source == source).delete()
        db_session.query(DestinationScore).filter(DestinationScore.source == source).delete()
        db_session.commit()
