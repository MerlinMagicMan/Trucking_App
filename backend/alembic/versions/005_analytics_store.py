"""005 — Analytics derived tables (Phase 3B)

Creates lane_statistics, market_statistics, destination_scores.
All derived from load_snapshots via batch jobs.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    # ---- lane_statistics ----
    op.create_table(
        "lane_statistics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("equipment_type", sa.Text(), nullable=True),
        sa.Column("origin_geohash", sa.Text(), nullable=False),
        sa.Column("destination_geohash", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("load_count", sa.Integer(), nullable=False),
        sa.Column("rate_p25", sa.Float(), nullable=True),
        sa.Column("rate_p50", sa.Float(), nullable=True),
        sa.Column("rate_p75", sa.Float(), nullable=True),
        sa.Column("rate_p90", sa.Float(), nullable=True),
        sa.Column("avg_miles", sa.Float(), nullable=True),
        sa.Column("avg_rate_per_mile", sa.Float(), nullable=True),
        sa.Column("time_to_cover_p50_minutes", sa.Float(), nullable=True),
        sa.Column("volatility_score", sa.Float(), nullable=True),
        sa.UniqueConstraint(
            "org_id", "origin_geohash", "destination_geohash",
            "equipment_type", "window_start", "window_end", "source",
            name="uq_lane_stat_window",
        ),
    )
    op.create_index("ix_lane_stat_lane_window", "lane_statistics", ["org_id", "origin_geohash", "destination_geohash", "window_end"])
    op.create_index("ix_lane_stat_window", "lane_statistics", ["org_id", "window_start", "window_end"])
    op.create_index("ix_lane_stat_computed", "lane_statistics", ["org_id", "computed_at"])

    # ---- market_statistics ----
    op.create_table(
        "market_statistics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("market_geohash", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("active_load_count_avg", sa.Float(), nullable=False),
        sa.Column("new_loads_count", sa.Integer(), nullable=False),
        sa.Column("expired_loads_count", sa.Integer(), nullable=False),
        sa.Column("reload_depth", sa.Float(), nullable=True),
        sa.Column("market_temperature", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "org_id", "market_geohash", "window_start", "window_end", "source",
            name="uq_market_stat_window",
        ),
    )
    op.create_index("ix_market_stat_geo_window", "market_statistics", ["org_id", "market_geohash", "window_end"])
    op.create_index("ix_market_stat_computed", "market_statistics", ["org_id", "computed_at"])

    # ---- destination_scores ----
    op.create_table(
        "destination_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("destination_geohash", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reload_probability", sa.Float(), nullable=True),
        sa.Column("avg_time_to_first_reload_minutes", sa.Float(), nullable=True),
        sa.Column("efficiency_score", sa.Float(), nullable=True),
        sa.Column("volatility_score", sa.Float(), nullable=True),
        sa.Column("explanation", JSONB(), nullable=True),
        sa.UniqueConstraint(
            "org_id", "destination_geohash", "window_start", "window_end", "source",
            name="uq_dest_score_window",
        ),
    )
    op.create_index("ix_dest_score_geo_window", "destination_scores", ["org_id", "destination_geohash", "window_end"])


def downgrade():
    op.drop_table("destination_scores")
    op.drop_table("market_statistics")
    op.drop_table("lane_statistics")
