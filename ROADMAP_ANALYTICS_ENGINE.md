# Analytics & Route Intelligence Engine — Implementation Roadmap

## For CTO Review

---

## Current State (What's Built)

| Layer | Status | Notes |
|-------|--------|-------|
| Plan-based decision engine | **Complete** | 2-3 load chains, profit/day, full economics |
| HOS feasibility + risk engine | **Complete** | Drive/on-duty/cycle, 4 risk types |
| Timeline + cost modeling | **Complete** | Gap-free timelines, 6 cost categories, audit trail |
| Multi-tenant spine | **Complete** | org_id everywhere, X-Org-Id header, seed data |
| Enterprise shell | **Complete** | Sidebar nav, org/truck selectors, Routes/Trucks/History pages |
| Connector abstraction | **Complete** | BaseConnector interface, Truckstop (mock), DAT (stub) |
| Audit/replay system | **Complete** | full_payload JSONB on every event, deterministic replay |

**What's missing**: Real data ingestion, analytics store, lane intelligence, market signals, negotiation metrics, and the intelligence APIs described in the data room.

---

## Proposed Phases

### Phase 3A: Data Ingestion Pipeline (Layer A + B from data room)

**Goal**: Replace mock JSON with live, scheduled load board ingestion. Store raw snapshots immutably.

#### New tables

```
load_snapshots
  id UUID PK
  org_id UUID
  source VARCHAR(50)        -- truckstop, dat, user_uploaded
  external_id VARCHAR(255)
  raw_payload JSONB          -- immutable original
  canonical JSONB            -- normalized CanonicalLoad
  ingested_at TIMESTAMP
  equipment VARCHAR(50)
  pickup_city, pickup_state
  delivery_city, delivery_state
  pickup_lat, pickup_lng
  delivery_lat, delivery_lng
  rate_total FLOAT
  miles FLOAT
  posted_at TIMESTAMP
  expires_at TIMESTAMP       -- when load disappears from board
  status VARCHAR(20)         -- active, expired, covered
```

#### New backend code

| File | Purpose |
|------|---------|
| `backend/app/ingestion/scheduler.py` | APScheduler or Celery beat — runs connectors every N minutes |
| `backend/app/ingestion/snapshot_store.py` | Writes raw + canonical to load_snapshots |
| `backend/app/connectors/truckstop.py` | Upgrade: real API calls (when credentials available), fallback to mock |
| `backend/app/connectors/dat.py` | Upgrade: real API calls (when credentials available) |
| `backend/app/ingestion/dedup.py` | Dedup by (source, external_id) — update status, don't duplicate |

#### Configuration

```
INGESTION_INTERVAL_MINUTES=15    # configurable per source
TRUCKSTOP_API_KEY=...
DAT_API_KEY=...
```

#### Key decisions

- Pull cadence: 15 min default, configurable per source
- Raw payload stored immutably — never mutated after ingestion
- Canonical normalization runs at ingestion time, stored alongside raw
- `expires_at` tracked: when a load disappears, mark it `covered` or `expired`
- load_snapshots replaces mock JSON as the data source for plan generation

#### Integration change

Plan generator and optimizer switch from `connector.search_loads()` to querying `load_snapshots` table directly (filtered by `status=active`, `org_id`, radius, equipment). Connectors become ingestion-only; the engine reads from the store.

---

### Phase 3B: Analytics Store + Lane Statistics (Layer C + D)

**Goal**: Build derived analytics tables that power intelligence APIs. Batch + near-real-time.

#### New tables

```
lane_statistics
  id UUID PK
  origin_city, origin_state
  dest_city, dest_state
  equipment VARCHAR(50)
  period_start DATE
  period_end DATE
  sample_count INT
  rate_p10 FLOAT
  rate_p25 FLOAT
  rate_p50 FLOAT              -- median
  rate_p75 FLOAT
  rate_p90 FLOAT
  rate_avg FLOAT
  miles_avg FLOAT
  rpm_p50 FLOAT               -- rate per mile median
  time_to_cover_hours_avg FLOAT
  time_to_cover_hours_p50 FLOAT
  posted_to_pickup_hours_avg FLOAT
  updated_at TIMESTAMP

market_statistics
  id UUID PK
  region VARCHAR(50)          -- metro area or state
  equipment VARCHAR(50)
  snapshot_date DATE
  active_loads INT
  loads_posted_24h INT
  loads_covered_24h INT
  avg_rate FLOAT
  avg_rpm FLOAT
  market_temperature VARCHAR(10)  -- cold, cool, balanced, warm, hot
  reload_depth INT            -- available loads within 100mi of major hubs
  updated_at TIMESTAMP

destination_scores
  id UUID PK
  city VARCHAR(100)
  state VARCHAR(10)
  equipment VARCHAR(50)
  period_start DATE
  period_end DATE
  reload_latency_hours_avg FLOAT   -- avg time to find next load after delivery
  reload_latency_hours_p50 FLOAT
  outbound_load_count INT          -- loads originating from this city
  avg_outbound_rate FLOAT
  avg_outbound_rpm FLOAT
  efficiency_score FLOAT           -- 0-100, composite
  updated_at TIMESTAMP
```

#### New backend code

| File | Purpose |
|------|---------|
| `backend/app/analytics/lane_analyzer.py` | Aggregates load_snapshots → lane_statistics (batch, daily) |
| `backend/app/analytics/market_analyzer.py` | Aggregates load_snapshots → market_statistics (near-real-time, hourly) |
| `backend/app/analytics/destination_scorer.py` | Computes destination_scores from historical reload patterns |
| `backend/app/analytics/scheduler.py` | Runs analytics jobs on schedule |

#### Analytics computation

**Lane statistics** (daily batch):
1. Group load_snapshots by (origin_city+state, dest_city+state, equipment, week)
2. Compute percentile distributions on rate_total
3. Compute time_to_cover from (posted_at → expires_at or covered_at)
4. Require minimum sample threshold (e.g. 5 loads) before publishing

**Market statistics** (hourly):
1. Count active loads per region
2. Compute 24h flow rates (posted vs covered)
3. Derive market_temperature: hot (demand >> supply), cold (supply >> demand)
4. Count reload_depth per hub city

**Destination scores** (daily):
1. For each delivery city: measure how quickly drivers find next loads
2. Compute from plan_generation_events + load_snapshots correlation
3. Score 0-100 based on reload speed, outbound rate, outbound volume

---

### Phase 3C: Intelligence APIs (Layer E)

**Goal**: Expose analytics as internal APIs consumed by Preflight, Copilot, TTC, Negotiation.

#### New endpoints

```
GET  /api/intel/lane?origin=OKC,OK&dest=Dallas,TX&equipment=reefer
  → { rate_p10, rate_p50, rate_p90, rpm_p50, time_to_cover, sample_count, confidence }

GET  /api/intel/market?region=TX&equipment=reefer
  → { active_loads, temperature, reload_depth, avg_rate, trend_7d }

GET  /api/intel/destination?city=Dallas&state=TX
  → { reload_latency_avg, outbound_loads, efficiency_score, best_outbound_lanes[] }

GET  /api/intel/negotiation?origin=OKC,OK&dest=Dallas,TX&rate_offered=850
  → { anchor_price, fast_accept, walk_away, market_position, justification }

GET  /api/intel/corridor?from=OKC,OK&to=Atlanta,GA&days=7
  → { recommended_route[], total_expected_profit, risk_assessment }
```

#### Negotiation intelligence logic

```python
def negotiate(origin, dest, rate_offered, equipment="reefer"):
    lane = get_lane_stats(origin, dest, equipment)
    market = get_market_stats(origin_region, equipment)

    anchor_price = lane.rate_p75          # aim high
    fast_accept = lane.rate_p50           # fair market
    walk_away = lane.rate_p25             # below this, not worth it

    if market.temperature == "hot":
        anchor_price = lane.rate_p90      # strong leverage
        justification = f"Market is hot. {market.active_loads} loads active, avg ${lane.rate_avg}."
    elif market.temperature == "cold":
        fast_accept = lane.rate_p25       # weaker position
        justification = f"Market is soft. Consider accepting at ${lane.rate_p25}+."

    position = "above_market" if rate_offered > lane.rate_p50 else "below_market"

    return { anchor_price, fast_accept, walk_away, position, justification }
```

#### Integration with existing modules

| Consumer | Intel endpoint used | Purpose |
|----------|-------------------|---------|
| Preflight | `/intel/destination` | Rank plans by destination reload efficiency |
| Preflight | `/intel/lane` | Show lane rate context on each load |
| Preflight | `/intel/market` | Market temperature badge on plan columns |
| Plan Generator | `/intel/destination` | Replace hardcoded reefer_hub_bonus with data-driven scores |
| Scoring Engine | `/intel/lane` | Replace rule-based scoring with market-informed scoring |
| Negotiation (new) | `/intel/negotiation` | Full negotiation assistant |
| Copilot (future) | `/intel/market` | Real-time market alerts |

---

### Phase 3D: Preflight Intelligence Integration

**Goal**: Wire intelligence into the existing Preflight UI so users see market context alongside plans.

#### UI changes

**PlanColumn** additions:
- Lane rate context: "This lane pays $2.10-$3.40/mi (you're at $2.85)"
- Destination score badge: "Dallas: A+ reload" / "Wichita Falls: C reload"
- Market temperature indicator: 🔥 Hot / ❄️ Cold / ⚖️ Balanced

**InspectPanel Economics tab** additions:
- Lane rate distribution chart (p10/p25/p50/p75/p90 with "you are here" marker)
- Historical rate trend (7d/30d if data available)
- Negotiation suggestion if rate < p50

**PreflightSetup sidebar** additions:
- Market conditions summary: "TX market is warm. 847 active reefer loads."
- Suggested radius adjustment based on market depth

#### Scoring engine upgrade

Replace hardcoded reefer hub bonuses with destination_scores:
```python
# Before (hardcoded)
if delivery_city in ["Dallas", "Houston"]: score += 8

# After (data-driven)
dest_score = get_destination_score(delivery_city, delivery_state)
score += dest_score.efficiency_score * 0.1  # 0-10 points based on real data
```

---

### Phase 4: Copilot (Plan Degradation + Branch Suggestions)

**Goal**: Real-time monitoring of active plans. Alert when conditions change. Suggest branches.

#### Concept

Once a driver starts executing a plan, the Copilot watches for:
- Load disappearing from the board (covered by someone else)
- Rate changes on planned loads
- New better loads appearing on the route
- Weather/traffic disruptions
- HOS running tighter than expected

When degradation is detected, Copilot suggests branch plans.

#### Dependencies

- Phase 3A (live ingestion) — must have real-time load data
- Phase 3B (market stats) — must know if conditions changed
- "Start Plan" feature (Phase 2B) — must know which plan is active

#### New components

| Component | Purpose |
|-----------|---------|
| `backend/app/copilot/monitor.py` | Watches active plans against current market |
| `backend/app/copilot/degradation.py` | Detects plan degradation (load gone, rate changed, etc.) |
| `backend/app/copilot/branch.py` | Generates alternative sub-plans from current position |
| `frontend/src/pages/CopilotPage.tsx` | Active plan view with alerts and branch suggestions |

---

### Phase 5: Maintenance & Cost Tracking

**Goal**: Track actual costs vs estimated. Build maintenance prediction.

#### Tables

```
actual_costs
  id UUID PK
  org_id UUID
  truck_id UUID
  plan_id UUID (nullable)
  cost_type VARCHAR(50)    -- fuel, toll, maintenance, tire, other
  amount_usd FLOAT
  odometer_miles INT
  recorded_at TIMESTAMP
  notes TEXT

maintenance_records
  id UUID PK
  org_id UUID
  truck_id UUID
  event_type VARCHAR(50)   -- oil_change, tire_rotation, brake, etc.
  odometer_miles INT
  cost_usd FLOAT
  performed_at TIMESTAMP
  next_due_miles INT
  notes TEXT
```

#### Value

- Actual vs estimated cost comparison → refine economics engine
- Maintenance prediction → surface in plan risk signals
- Fleet-level cost analytics → enterprise reporting

---

### Phase 6: TTC (Truck Traffic Control)

**Goal**: Fleet-level orchestration. Multiple trucks, coordinated planning.

#### Concept

For fleets with 5+ trucks:
- See all trucks on a map
- Generate plans for each truck considering fleet-wide optimization
- Avoid sending 3 trucks to the same destination
- Coordinate pickups at same shipper

#### Dependencies

- Phase 3A-3C (market intelligence)
- Phase 4 (Copilot per truck)
- Fleet-level truck management (Phase 2A — done)

---

### Phase 7: Auth + Roles

**Goal**: Add authentication last, not first. Multi-tenant spine already enforces scoping.

#### Approach

- OAuth2 / JWT tokens
- Roles: owner, dispatcher, driver, viewer
- Map authenticated user → org_id (replace X-Org-Id header)
- No data model changes — org_id already on everything

---

## Implementation Sequencing

```
Phase 3A: Data Ingestion Pipeline
  ├── Prerequisite: Load board API credentials
  ├── Duration: Core tables + scheduler + connector upgrades
  ├── Deliverable: load_snapshots table filling with real data
  └── Validation: Can see live loads in Routes Library

Phase 3B: Analytics Store + Lane Statistics
  ├── Prerequisite: Phase 3A (need data to analyze)
  ├── Duration: Analytics jobs + derived tables
  ├── Deliverable: lane_statistics, market_statistics, destination_scores populated
  └── Validation: Can query lane stats for any OKC→Dallas route

Phase 3C: Intelligence APIs
  ├── Prerequisite: Phase 3B (need analytics to expose)
  ├── Deliverable: /intel/* endpoints returning real market data
  └── Validation: /intel/lane returns percentiles, /intel/negotiation returns prices

Phase 3D: Preflight Intelligence Integration
  ├── Prerequisite: Phase 3C
  ├── Deliverable: Plans show market context, rates, destination scores
  └── Validation: PlanColumn shows lane rate range, destination reload grade

Phase 4: Copilot
  ├── Prerequisite: Phase 3A + "Start Plan" (Phase 2B)
  ├── Deliverable: Active plan monitoring + branch suggestions
  └── Validation: Alert fires when a planned load disappears

Phase 5: Maintenance & Cost Tracking
  ├── Prerequisite: Phase 2A (multi-tenant — done)
  ├── Can run in parallel with Phase 3
  ├── Deliverable: Actual cost tracking, maintenance prediction
  └── Validation: Economics engine uses real cost data

Phase 6: TTC
  ├── Prerequisite: Phase 3 + Phase 4
  ├── Deliverable: Fleet-level planning dashboard
  └── Validation: 5 trucks planned simultaneously

Phase 7: Auth
  ├── Prerequisite: All above stable
  ├── Deliverable: Login, roles, token-based org resolution
  └── Validation: X-Org-Id replaced by JWT-derived org_id
```

---

## Critical Path

**The bottleneck is Phase 3A** — everything downstream needs real data.

Without live ingestion:
- Analytics tables stay empty
- Intelligence APIs return nothing
- Negotiation has no market context
- Copilot can't detect changes
- Destination scores are guesses

**Recommendation**: Start Phase 3A immediately. Even with mock data on a scheduler (simulating ingestion cadence and snapshot storage), the pipeline architecture gets validated and all downstream phases can develop against synthetic analytics.

---

## What Can Run in Parallel

| Track | Phases | Dependencies |
|-------|--------|-------------|
| **Data track** | 3A → 3B → 3C | Sequential (each needs prior) |
| **UI track** | 3D (once 3C has stubs) | Can stub intel APIs early |
| **Cost track** | 5 | Independent, can start now |
| **Copilot track** | 4 | Needs 3A + "Start Plan" |

**Maximum parallelism**: Run Phase 5 alongside Phase 3A. Stub intel APIs for Phase 3D frontend work while 3B/3C are in progress.

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Load board API access delayed | Blocks 3A with real data | Build pipeline with mock scheduler first |
| Analytics computations too slow | Blocks 3B | Use materialized views, incremental aggregation |
| Sample sizes too small for stats | Bad intelligence | Enforce minimum thresholds, show confidence levels |
| Ingestion volume exceeds DB capacity | Performance degradation | Partition load_snapshots by month, archive old data |
| Intelligence wrong / misleading | Trust damage | Always show confidence + sample size, never hide uncertainty |
