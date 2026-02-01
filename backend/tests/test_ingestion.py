"""
Tests for Phase 3A: Data Ingestion Pipeline
"""
import pytest
from datetime import datetime, timedelta

from app.connectors.mock_market import MockMarketConnector, _is_active, _LOAD_TEMPLATES


class TestMockMarketConnector:
    """Tests for MockMarketConnector."""

    def test_search_loads_returns_loads(self):
        connector = MockMarketConnector()
        raw_loads, metadata = connector.search_loads(35.4676, -97.5164)
        assert isinstance(raw_loads, list)
        assert len(raw_loads) > 0
        assert metadata["connector"] == "mock_market"

    def test_loads_have_stable_external_ids(self):
        connector = MockMarketConnector()
        loads1, _ = connector.search_loads(35.4676, -97.5164)
        loads2, _ = connector.search_loads(35.4676, -97.5164)
        ids1 = {l["id"] for l in loads1}
        ids2 = {l["id"] for l in loads2}
        # Same time slot → same loads
        assert ids1 == ids2

    def test_normalize_produces_canonical_load(self):
        connector = MockMarketConnector()
        raw_loads, _ = connector.search_loads(35.4676, -97.5164)
        assert len(raw_loads) > 0
        canonical = connector.normalize(raw_loads[0])
        assert canonical.source == "mock_market"
        assert canonical.rate_total > 0
        assert canonical.pickup.city

    def test_health_check(self):
        connector = MockMarketConnector()
        health = connector.health_check()
        assert health["status"] == "ok"
        assert health["loads_available"] > 0

    def test_subset_selection_deterministic(self):
        """Same slot → same active subset."""
        slot = 12345
        active1 = [t["ext"] for t in _LOAD_TEMPLATES if _is_active(t["ext"], slot)]
        active2 = [t["ext"] for t in _LOAD_TEMPLATES if _is_active(t["ext"], slot)]
        assert active1 == active2

    def test_different_slots_may_differ(self):
        """Different slots should produce at least some different subsets."""
        sets = []
        for slot in range(100, 110):
            active = frozenset(t["ext"] for t in _LOAD_TEMPLATES if _is_active(t["ext"], slot))
            sets.append(active)
        # Not all identical (would be extremely unlikely)
        assert len(set(sets)) > 1


class TestSnapshotStore:
    """Tests for snapshot_store — requires DB, skip if unavailable."""

    @pytest.fixture
    def db_session(self):
        """Try to get a DB session; skip if unavailable."""
        try:
            from app.db.connection import SessionLocal, engine, Base
            Base.metadata.create_all(bind=engine)
            db = SessionLocal()
            yield db
            db.rollback()
            db.close()
        except Exception:
            pytest.skip("Database not available")

    def test_upsert_and_query(self, db_session):
        from app.ingestion.snapshot_store import upsert_snapshot, get_active_loads
        from app.models.snapshot import LoadSnapshot

        org_id = "00000000-0000-0000-0000-000000000001"

        # Clean up any existing test data
        db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "TEST-001",
        ).delete()
        db_session.commit()

        canonical = {
            "id": "test_TEST-001",
            "source": "test",
            "external_id": "TEST-001",
            "posted_at": datetime.utcnow().isoformat(),
            "equipment": "reefer",
            "pickup": {"city": "Dallas", "state": "TX", "lat": 32.7767, "lng": -96.7970},
            "delivery": {"city": "Houston", "state": "TX", "lat": 29.7604, "lng": -95.3698},
            "rate_total": 900.0,
            "miles": 239,
        }

        upsert_snapshot(
            db=db_session,
            org_id=org_id,
            source="test",
            external_id="TEST-001",
            raw_payload={"raw": True},
            canonical_dict=canonical,
        )
        db_session.commit()

        # Query — should find the load within radius
        loads = get_active_loads(db_session, org_id, truck_lat=32.7, truck_lng=-96.8, radius_miles=50)
        assert any(l.external_id == "TEST-001" for l in loads)

        # Cleanup
        db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "TEST-001",
        ).delete()
        db_session.commit()

    def test_upsert_dedup(self, db_session):
        from app.ingestion.snapshot_store import upsert_snapshot
        from app.models.snapshot import LoadSnapshot

        org_id = "00000000-0000-0000-0000-000000000001"

        # Clean up
        db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "DEDUP-001",
        ).delete()
        db_session.commit()

        canonical = {
            "id": "test_DEDUP-001",
            "source": "test",
            "external_id": "DEDUP-001",
            "posted_at": datetime.utcnow().isoformat(),
            "equipment": "reefer",
            "pickup": {"city": "OKC", "state": "OK", "lat": 35.46, "lng": -97.51},
            "delivery": {"city": "Dallas", "state": "TX", "lat": 32.77, "lng": -96.79},
            "rate_total": 800.0,
            "miles": 200,
        }

        # Insert twice
        upsert_snapshot(db_session, org_id, "test", "DEDUP-001", {"v": 1}, canonical)
        db_session.commit()
        upsert_snapshot(db_session, org_id, "test", "DEDUP-001", {"v": 2}, canonical)
        db_session.commit()

        count = db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "DEDUP-001",
        ).count()
        assert count == 1, f"Expected 1 row after dedup, got {count}"

        # Verify raw_payload is still v1 (immutable)
        row = db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "DEDUP-001",
        ).first()
        assert row.raw_payload.get("v") == 1

        # Cleanup
        db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "DEDUP-001",
        ).delete()
        db_session.commit()

    def test_expire_stale(self, db_session):
        from app.ingestion.snapshot_store import upsert_snapshot, expire_stale
        from app.models.snapshot import LoadSnapshot

        org_id = "00000000-0000-0000-0000-000000000001"

        # Clean up
        db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "EXPIRE-001",
        ).delete()
        db_session.commit()

        canonical = {
            "id": "test_EXPIRE-001",
            "source": "test",
            "external_id": "EXPIRE-001",
            "posted_at": datetime.utcnow().isoformat(),
            "equipment": "reefer",
            "pickup": {"city": "OKC", "state": "OK", "lat": 35.46, "lng": -97.51},
            "delivery": {"city": "Dallas", "state": "TX", "lat": 32.77, "lng": -96.79},
            "rate_total": 700.0,
            "miles": 200,
        }

        upsert_snapshot(db_session, org_id, "test", "EXPIRE-001", {"raw": True}, canonical)
        db_session.commit()

        # Manually backdate ingested_at
        row = db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "EXPIRE-001",
        ).first()
        row.ingested_at = datetime.utcnow() - timedelta(hours=2)
        db_session.commit()

        expired_count = expire_stale(db_session, org_id, source="test", older_than_minutes=60)
        db_session.commit()
        assert expired_count >= 1

        row = db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "EXPIRE-001",
        ).first()
        assert row.status == "expired"

        # Cleanup
        db_session.query(LoadSnapshot).filter(
            LoadSnapshot.source == "test",
            LoadSnapshot.external_id == "EXPIRE-001",
        ).delete()
        db_session.commit()
