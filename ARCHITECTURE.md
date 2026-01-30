# Architecture Overview

## System Diagram

```
┌─────────────────┐
│  Mobile Browser │
│   (React SPA)   │
└────────┬────────┘
         │ HTTPS
         ▼
┌──────────────────────────────────────┐
│         FastAPI Backend              │
│  ┌────────────────────────────────┐  │
│  │   POST /api/optimize           │  │
│  │   GET  /api/health             │  │
│  │   GET  /api/connectors/health  │  │
│  └────────────┬───────────────────┘  │
│               │                      │
│      ┌────────▼────────┐             │
│      │ Optimization    │             │
│      │   Engine        │             │
│      └────────┬────────┘             │
│               │                      │
│    ┌──────────┴──────────┐           │
│    │                     │           │
│    ▼                     ▼           │
│  ┌────────────┐    ┌──────────┐     │
│  │ HOS        │    │ Scoring  │     │
│  │ Checker    │    │ Engine   │     │
│  └────────────┘    └──────────┘     │
│         │                │           │
│         └────────┬───────┘           │
│                  ▼                   │
│         ┌─────────────────┐          │
│         │   Connectors    │          │
│         │  - Truckstop    │          │
│         │  - DAT (stub)   │          │
│         └────────┬────────┘          │
└──────────────────┼──────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │   PostgreSQL    │
         │  (Audit Logs)   │
         └─────────────────┘
```

## Data Flow

### 1. User Submits Truck Snapshot

**User Input** → **Frontend** → **POST /api/optimize**

```
TruckSnapshot {
  current_lat: 35.4676,
  current_lng: -97.5164,
  hos: {
    drive_remaining_min: 660,
    on_duty_remaining_min: 840,
    cycle_remaining_min: 4200
  }
}
```

### 2. Backend Processing

```
API Endpoint
    ↓
OptimizationEngine.optimize()
    ↓
┌─────────────────────────────────────┐
│ 1. Fetch Loads from Connectors     │
│    - Search within radius           │
│    - Normalize to CanonicalLoad     │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. Filter by HOS Feasibility        │
│    - Calculate drive time           │
│    - Check against HOS limits       │
│    - DISCARD infeasible loads       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. Score Feasible Loads             │
│    - Deadhead penalty               │
│    - Reefer hub bonus               │
│    - Time band bonus                │
│    - Appointment risk penalty       │
│    → reload_score (0-100)           │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. Generate Explanations            │
│    - Minimum 3 per load             │
│    - Plain English reasons          │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 5. Rank and Return Top 3            │
│    - Sort by reload_score DESC      │
│    - Take top 3 (or fewer)          │
│    - Create forward-look timeline   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 6. Audit Log to PostgreSQL          │
│    - Full request/response payload  │
│    - Queryable for debugging        │
└─────────────────────────────────────┘
```

### 3. Response to Frontend

```json
OptimizeResponse {
  snapshot_id: "uuid",
  recommendations: [
    { rank: 1, reload_score: 85, explanations: [...] },
    { rank: 2, reload_score: 78, explanations: [...] },
    { rank: 3, reload_score: 72, explanations: [...] }
  ],
  forward_look: { events: [...] },
  warnings: [],
  loads_analyzed: 25,
  loads_feasible: 18
}
```

---

## Phase 0: Plan-Based Operating System

**Mission**: Transform single-load optimization into a multi-day, multi-load Plan-based decision engine.

**Core Philosophy**: **Plans, not loads, are the primary decision unit** for strategic trucking operations.

### System Diagram (Phase 0)

```
┌─────────────────┐
│  Desktop/Mobile │
│   (React SPA)   │
└────────┬────────┘
         │ HTTPS
         ▼
┌──────────────────────────────────────────────────┐
│              FastAPI Backend                     │
│  ┌────────────────────────────────────────────┐  │
│  │   POST /api/optimize         (MVP)        │  │
│  │   POST /api/plans/generate   (Phase 0) 🆕 │  │
│  │   GET  /api/health                        │  │
│  │   GET  /api/connectors/health             │  │
│  └────────────┬───────────────────────────────┘  │
│               │                                  │
│      ┌────────┴────────┐                         │
│      ▼                 ▼                         │
│  ┌─────────────┐  ┌─────────────────┐            │
│  │ Optimization│  │ Plan Generator  │ 🆕         │
│  │   Engine    │  │  - TimeEngine   │            │
│  │   (MVP)     │  │  - Economics    │            │
│  └──────┬──────┘  │  - RiskEngine   │            │
│         │         │  - Explanations │            │
│         │         └────────┬────────┘            │
│         │                  │                     │
│    ┌────┴────────┬─────────┴──────┐              │
│    ▼             ▼                ▼              │
│  ┌────────┐  ┌────────┐    ┌──────────┐         │
│  │  HOS   │  │Scoring │    │  Reuses  │         │
│  │Checker │  │Engine  │    │    MVP   │         │
│  └────────┘  └────────┘    │  Engines │         │
│         │         │         └──────────┘         │
│         └─────────┼────────────────┘             │
│                   ▼                              │
│         ┌──────────────────┐                     │
│         │   Connectors     │                     │
│         │  - Truckstop     │                     │
│         │  - DAT (stub)    │                     │
│         └─────────┬────────┘                     │
└───────────────────┼──────────────────────────────┘
                    │
                    ▼
         ┌─────────────────────────────┐
         │       PostgreSQL            │
         │  - recommendation_events    │
         │  - plan_generation_events 🆕│
         │  - cost_configuration 🆕     │
         └─────────────────────────────┘
```

### Plan as Primary Abstraction

A **Plan** is a complete multi-day strategy containing:

```python
Plan {
    plan_id: UUID                           # Unique identifier
    loads: List[LoadInPlan]                 # 2-3 chained loads
    profit_per_day_usd: float               # KEY METRIC for comparison
    net_profit_usd: float                   # Total profit over horizon
    total_revenue_usd: float                # Sum of all load rates
    total_costs_usd: float                  # Sum of all expenses
    time_blocks: List[TimeBlock]            # Complete timeline
    financial_events: List[FinancialEvent]  # Every revenue + cost
    risk_signals: List[RiskSignal]          # Explicit risk assessment
    explanations: List[str]                 # ≥3 plain-English reasons
    confidence: str                         # high/medium/low
    plan_score: int                         # 0-100 overall quality
    end_location_name: str                  # Where plan leaves driver
    # ... metadata
}
```

**Key Components**:

1. **LoadInPlan**: Extends CanonicalLoad with plan-specific context
   - `load`: The canonical load
   - `sequence_number`: Position in chain (1, 2, or 3)
   - `pickup_eta`, `delivery_eta`: Projected timestamps
   - `hos_snapshot_before`, `hos_snapshot_after`: State tracking
   - `estimated_deadhead_miles`, `estimated_loaded_miles`
   - `estimated_total_time_min`

2. **TimeBlock**: Explicit time modeling for every minute
   - `block_type`: drive, waiting, loading, unloading, rest, available
   - `start_time`, `end_time`: ISO timestamps
   - `duration_min`: Block length
   - `description`: Human-readable (e.g., "Drive from OKC to Dallas pickup")
   - `location_lat`, `location_lng`: Where block occurs
   - `associated_load_id`: Links to LoadInPlan

3. **FinancialEvent**: Transparent cost/revenue tracking
   - `event_type`: revenue, fuel_cost, toll_cost, waiting_cost, maintenance_reserve, opportunity_cost
   - `amount_usd`: Signed value (+ revenue, - costs)
   - `timestamp`: When event occurs
   - `calculation_details`: Full formula transparency
   - `associated_load_id`: Links to LoadInPlan

4. **RiskSignal**: Explicit risk assessment
   - `risk_type`: hos_tight, appointment_tight, market_weak, deadhead_high
   - `severity`: low, medium, high
   - `description`: Plain-English explanation
   - `associated_load_id`: Optional load linkage

### Multi-Load Plan Generation Data Flow

```
User Submits TruckSnapshot
    ↓
POST /api/plans/generate?planning_horizon_days=7&max_plans=3&radius_miles=250
    ↓
PlanGenerator.generate_plans()
    ↓
┌──────────────────────────────────────────────────────┐
│ 1. Get First Load Candidates                         │
│    - Reuse MVP OptimizationEngine                    │
│    - Find top 5 HOS-feasible loads                   │
│    - Sort by reload_score DESC, then id ASC          │
│    → Deterministic candidate set                     │
└──────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────┐
│ 2. Build Two-Load Plans (5 × 3 = 15 plans)          │
│    For each first load:                              │
│      - Simulate truck state after completion         │
│      - Find top 3 second loads from new position     │
│      - Create two-load plan                          │
│    → Prune to top 5 by profit_per_day                │
└──────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────┐
│ 3. Build Three-Load Plans (5 × 2 = 10 plans)        │
│    For top 5 two-load plans:                         │
│      - Simulate truck state after second load        │
│      - Find top 2 third loads from new position      │
│      - Create three-load plan                        │
│    → Combine with two-load plans                     │
└──────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────┐
│ 4. Build Complete Plans (for top candidates)        │
│    For each load sequence:                           │
│      - TimeEngine: Generate TimeBlocks               │
│      - EconomicsEngine: Calculate FinancialEvents    │
│      - RiskEngine: Assess RiskSignals                │
│      - Generate ≥3 explanations                      │
│      - Calculate profit_per_day                      │
└──────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────┐
│ 5. Select Diverse Plans (0-3 final plans)           │
│    - Sort by profit_per_day DESC, plan_id ASC       │
│    - Take #1 (highest profit/day)                    │
│    - Take #2 if different end location or strategy  │
│    - Take #3 if adds strategic diversity            │
│    → Ensures user sees real alternatives            │
└──────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────┐
│ 6. Audit Log to PostgreSQL                          │
│    - plan_generation_events table                    │
│    - Full request/response in JSONB                  │
│    - All plans generated (not just final selection)  │
│    → Complete replay capability                      │
└──────────────────────────────────────────────────────┘
    ↓
GeneratePlansResponse {
    snapshot_id: UUID,
    plans: [Plan, Plan, Plan],  // 0-3 plans
    warnings: [...],
    metadata: { planning_horizon_days, radius_miles, ... }
}
```

### Economics Engine: Full Cost Transparency

**Purpose**: Calculate true net profit with complete cost breakdown.

**Cost Model** (`EconomicsEngine`):

```python
# Revenue Events
+ Load 1 rate_total
+ Load 2 rate_total
+ Load 3 rate_total (if present)

# Cost Events (all with calculation_details)
- Fuel Cost:          total_miles × $0.85/mile
- Toll Cost:          route_miles × $0.12/mile (OK/TX/KS corridors)
- Waiting Cost:       waiting_hours × $35/hour
- Maintenance Reserve: total_miles × $0.15/mile (PM, tires, repairs)
- Opportunity Cost:   idle_days × $500/day (baseline earnings target)

# Financial Outcome
Net Profit = Total Revenue - Total Costs
Profit Per Day = Net Profit / planning_horizon_days
```

**FinancialEvent Example**:

```json
{
  "event_type": "fuel_cost",
  "amount_usd": -238.00,
  "timestamp": "2026-01-30T14:00:00Z",
  "calculation_details": "280 total miles × $0.85/mile = $238.00 fuel cost",
  "associated_load_id": "load_1"
}
```

**Transparency Requirement**: Every FinancialEvent includes `calculation_details` showing exact formula used.

**Configuration**: Cost parameters stored in `cost_configuration` table with `effective_date` for historical accuracy.

### TimeEngine: Complete Timeline Modeling

**Purpose**: Account for every minute in the planning horizon.

**TimeBlock Types**:

1. **drive**: Deadhead or loaded driving
   - Duration: `distance_miles / 50mph × 60`
   - HOS impact: Consumes drive time and on-duty time

2. **waiting**: Time between arrival and appointment
   - Duration: `pickup/delivery window - arrival_time`
   - Cost impact: `waiting_hours × $35/hour`

3. **loading**: At pickup location
   - Duration: Fixed 90 minutes (configurable)
   - HOS impact: On-duty time

4. **unloading**: At delivery location
   - Duration: Fixed 90 minutes (configurable)
   - HOS impact: On-duty time

5. **rest**: Mandatory 10-hour break
   - Duration: 600 minutes
   - HOS reset: Drive and on-duty timers reset

6. **available**: Idle time waiting for next load
   - Duration: Gap between delivery and next pickup
   - Opportunity cost if >24 hours

**Timeline Guarantees**:

- ✅ **Chronological**: Blocks sorted by start_time
- ✅ **Gap-free**: Every minute from now → horizon covered
- ✅ **HOS-compliant**: No block exceeds legal limits
- ✅ **Transparent**: Every block has human-readable description

### RiskEngine: Explicit Risk Assessment

**Purpose**: Surface potential issues before driver commits to plan.

**Risk Types**:

1. **hos_tight**: Drive or on-duty time <10% remaining
   - Severity: `high` if <5%, `medium` if <10%, `low` if <20%
   - Description: "Drive time will be tight after Load 2 (only 45 minutes remaining)"

2. **appointment_tight**: Arrival <1 hour before window
   - Severity: `high` if <30min buffer, `medium` if <60min
   - Description: "Only 40-minute buffer before Dallas pickup window - traffic risk"

3. **market_weak**: Delivery into low-freight area
   - Severity: Based on reload_score of delivery location
   - Description: "Delivers into Wichita Falls (weak reefer market) - next load uncertain"

4. **deadhead_high**: Empty miles >150
   - Severity: `high` if >200mi, `medium` if >150mi
   - Description: "180-mile deadhead to next pickup consumes profit margin"

**Risk Philosophy**: Conservative. Better to surface 5 low-severity warnings than miss 1 high-severity risk.

### Determinism Guarantees

**Critical Requirement**: Same TruckSnapshot → Identical Plans (every time)

**Implementation**:

1. **Load Candidate Ordering**:
   ```python
   # Always sort by reload_score DESC, then id ASC
   candidates.sort(key=lambda r: (-r.reload_score, r.load.id))
   ```

2. **Plan Ranking**:
   ```python
   # Always sort by profit_per_day DESC, then plan_id ASC
   plans.sort(key=lambda p: (-p.profit_per_day_usd, str(p.plan_id)))
   ```

3. **No Random Elements**:
   - No `random.choice()`
   - No timestamp-based tie-breaking
   - No unordered dictionary iteration over load candidates

4. **Stable UUIDs** (for testing):
   - Use UUID5 with deterministic namespace + input hash
   - Production uses UUID4 but same-session requests are deterministic

5. **Pruning Strategy**:
   - First loads: Top 5 by score
   - Second loads: Top 3 per first load
   - Third loads: Top 2 per two-load plan
   - Final selection: Top 3 with diversity

**Validation**: `test_plans_are_deterministic()` runs same request twice, asserts byte-identical output.

### Audit and Replay Capability

**Database Schema** (`plan_generation_events`):

```sql
CREATE TABLE plan_generation_events (
    snapshot_id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    truck_location GEOGRAPHY(POINT),
    planning_horizon_days INTEGER,
    max_plans_requested INTEGER,
    radius_miles INTEGER,
    plans_generated INTEGER,
    full_payload JSONB NOT NULL,  -- Complete request + response
    INDEX (timestamp),
    INDEX (plans_generated)
);
```

**Replay Process**:

1. Query `plan_generation_events` by `snapshot_id`
2. Extract `full_payload.request`
3. Re-run `PlanGenerator.generate_plans()` with same inputs
4. Compare output to `full_payload.response`
5. Assert identical results (determinism validation)

**Use Cases**:

- **Debugging**: "Why did user get 0 plans yesterday?"
- **Regression Testing**: "Did the engine change behavior between versions?"
- **Cost Analysis**: "How much profit did plans generate over Q1?"
- **Model Training**: Historical plan quality → ML features

### Backward Compatibility Architecture

**Design Principle**: Phase 0 adds capabilities, **does not modify** MVP.

**Zero-Change Files** (MVP untouched):

- `app/engine/optimizer.py` - Reused as-is by PlanGenerator
- `app/engine/scoring.py` - Same reload_score logic
- `app/engine/hos_checker.py` - Same feasibility checks
- `app/engine/explanations.py` - Same explanation generation
- All MVP tests continue to pass

**New Files** (Phase 0):

- `app/models/plan.py` - Plan, TimeBlock, FinancialEvent, RiskSignal
- `app/engine/plan_generator.py` - Multi-load chaining orchestrator
- `app/engine/economics.py` - Full cost modeling
- `app/engine/time_engine.py` - Timeline generation
- `app/engine/risk_engine.py` - Risk assessment
- `app/engine/plan_explanations.py` - Plan-level explanations

**Endpoint Coexistence**:

- `POST /api/optimize` - MVP single-load (unchanged)
- `POST /api/plans/generate` - Phase 0 multi-load (new)

Users choose which endpoint based on need:

- **Simple decision** (next load only): Use `/api/optimize`
- **Strategic planning** (7-14 day horizon): Use `/api/plans/generate`

**Database Isolation**:

- `recommendation_events` - MVP audit logs (unchanged)
- `plan_generation_events` - Phase 0 audit logs (new table)
- `cost_configuration` - Phase 0 economics config (new table)

No migration required for existing MVP data.

### Phase 0 Key Metrics

**Plan Quality Indicators**:

- `profit_per_day_usd`: Primary ranking metric
- `plan_score`: 0-100 overall quality (accounts for profit + risk + market position)
- `confidence`: high/medium/low based on data quality
- `end_location_name`: Strategic positioning for next planning cycle

**System Health Metrics**:

- Plans generated per request: 0-3 (target: 2-3)
- Average profit_per_day: $250-$400 target for reefer
- Determinism verification: 100% identical on replay
- Timeline gaps: 0 (must be gap-free)
- Financial integrity: `sum(financial_events) == net_profit`

**Performance Targets**:

- Plan generation: <3 seconds for 7-day horizon
- Database audit log write: <100ms
- Frontend render: <2 seconds for 3 plans with full timelines

---

## Core Components

### Backend

#### 1. Canonical Models (`app/models/canonical.py`)

**Purpose**: Define vendor-neutral data structures.

**Key Models**:
- `CanonicalLoad`: Normalized load representation (source-agnostic)
- `TruckSnapshot`: Point-in-time truck state (location + HOS)
- `Recommendation`: Scored load with explanations
- `OptimizeResponse`: API response with top 3 + metadata

**Why**: Decouples optimization engine from vendor-specific formats.

#### 2. Connector Framework (`app/connectors/`)

**Purpose**: Pluggable interface for load board APIs.

**Interface** (`BaseConnector`):
```python
class BaseConnector(ABC):
    def search_loads(truck_lat, truck_lng, radius_miles) -> (raw_loads, metadata)
    def normalize(raw_load) -> CanonicalLoad
    def health_check() -> dict
```

**Implementations**:
- **TruckstopConnector**: Reads mock JSON (MVP), will integrate real API
- **DatConnector**: Stub (returns empty for now)

**Why**: Easily add new load sources without changing engine logic.

#### 3. HOS Checker (`app/engine/hos_checker.py`)

**Purpose**: Enforce legal driving hours constraints.

**Logic**:
```
deadhead_time = distance_to_pickup / 50mph
loaded_time = loaded_distance / 50mph
total_drive = deadhead_time + loaded_time
total_onduty = total_drive + loading(1.5hr) + unloading(1.5hr) + buffer(0.5hr)

feasible = total_drive <= hos.drive_remaining AND
           total_onduty <= hos.on_duty_remaining AND
           total_onduty <= hos.cycle_remaining
```

**Critical Rule**: Infeasible loads are filtered BEFORE scoring. They never reach top 3.

#### 4. Scoring Engine (`app/engine/scoring.py`)

**Purpose**: Calculate reload probability (0-100).

**Formula**:
```python
base_score = 100
score -= deadhead_miles * 1.5           # Penalty for empty miles
score -= appointment_risk_penalty        # 0-20 based on tight window
score += reefer_hub_bonus                # +8 for major hubs
score += time_band_bonus                 # +5 for 6am-2pm deliveries
score = clamp(score, 0, 100)
```

**Reefer Hubs** (high reload probability):
- Dallas/Fort Worth, TX
- Houston, TX
- Kansas City, MO/KS
- Phoenix, AZ
- Atlanta, GA

**Strong Time Bands**:
- 6am-10am: Morning deliveries → best reload potential
- 11am-2pm: Early afternoon → good same-day reload

**Why Not OK Boost?**: Per CTO guidance, no automatic Oklahoma bonus. Reload score is based on market fundamentals, not home bias.

#### 5. Explanation Generator (`app/engine/explanations.py`)

**Purpose**: Generate plain-English reasons (≥3 per load).

**Example Output**:
```
1. "Excellent 45-mile deadhead to pickup"
2. "Delivers into Dallas reefer hub in morning - excellent reload potential"
3. "Comfortable 2-hour buffer before pickup window"
4. "Uses only 65% of available drive time - leaves HOS margin"
```

**Why**: Drivers need to understand *why* a load is recommended, not just *what* the score is.

#### 6. Optimization Engine (`app/engine/optimizer.py`)

**Purpose**: Orchestrate entire flow.

**Guarantees**:
- **Deterministic**: Same TruckSnapshot → same top 3 (sorts by ID for tie-breaking)
- **HOS-Safe**: Infeasible loads never appear
- **Bounded Scores**: All reload_scores 0-100
- **Explainable**: Every recommendation has ≥3 reasons

### Frontend

#### Mobile-First Design Principles

1. **Single Column**: No horizontal scrolling
2. **Thumb-Friendly**: Minimum 44px tap targets
3. **Large Fonts**: 16px minimum for readability
4. **Progressive Disclosure**: "Why this?" expanders keep cards compact

#### Three-Screen Flow

1. **TruckSnapshotPage**: Location + HOS input
2. **RecommendationsPage**: Top 3 cards with scores/explanations
3. **ForwardLookPage**: 24-48 hour timeline

#### State Management

- Uses React Query for server state
- `sessionStorage` for navigation between screens
- No Redux (overkill for MVP)

### Database

#### Audit Logging

**Table**: `recommendation_events`

**Fields**:
- `snapshot_id`: Links to optimization request
- `timestamp`: When request occurred
- `connector`: Which load source was used
- `input_load_ids`: All loads considered
- `output_top3`: Final recommendations
- `full_payload`: Complete request/response (JSONB)

**Why**: Debug issues, replay scenarios, track system behavior.

## Key Design Decisions

### 1. Canonical Model Abstraction

**Decision**: All connectors normalize to `CanonicalLoad` before optimization.

**Why**:
- Engine doesn't care if load came from Truckstop, DAT, or future sources
- Adding new connectors doesn't require engine changes
- Testing is easier (mock canonical loads, not vendor formats)

**Trade-off**: Normalization layer adds complexity, but isolation is worth it.

### 2. HOS Filtering BEFORE Scoring

**Decision**: Discard infeasible loads immediately, never let them reach ranking.

**Why**:
- Simplifies scoring (don't need "infeasibility penalty")
- Guarantees safety (can't accidentally recommend illegal load)
- Clearer to drivers (only see loads they can actually take)

**Trade-off**: None. This is a hard requirement.

### 3. Deterministic Scoring

**Decision**: Same input always produces same output.

**Why**:
- Reproducible debugging
- Predictable for drivers (refresh doesn't change results)
- Testable (can write deterministic fixtures)

**Implementation**: Sort loads by `id` before scoring to ensure stable ordering.

### 4. Reefer Hub Intelligence Over Home Bias

**Decision**: Favor known reefer markets (Dallas, Houston, KC) instead of Oklahoma.

**Why**: Reload probability is about freight density, not driver preference. Dallas has more reefer freight than Oklahoma, even if Oklahoma is "home."

**CTO Guidance**: "Do not automatically boost Oklahoma just because it is home."

### 5. Conservative Explanations

**Decision**: Minimum 3 explanations per load, written in plain English.

**Why**: Drivers are stressed humans making high-stakes decisions. They need to understand *why*, not just trust a black-box score.

**Examples of What NOT to Do**:
- "Score: 85" (no context)
- "Good market dynamics" (vague)
- "Optimal route efficiency parameters aligned" (jargon)

**Examples of What to Do**:
- "Short 45-mile deadhead saves fuel and time"
- "Delivers into Dallas at 8am - reefer hub with strong morning reload activity"
- "2-hour buffer before pickup window reduces stress"

### 6. Warnings Over Failures

**Decision**: When <3 feasible loads exist, return what's available + warning.

**Why**: Better to show 1 good load + explanation than fail with "no results."

**Example**:
```json
{
  "recommendations": [{ "rank": 1, ... }],
  "warnings": [
    "Only 1 HOS-feasible load found (need 3 for full recommendations). Consider wider search radius or rest break."
  ]
}
```

## Testing Strategy

### Unit Tests

**File**: `backend/tests/test_engine.py`

**Critical Tests**:
1. `test_no_infeasible_loads_in_recommendations`: HOS check
2. `test_reload_score_bounds`: 0-100 validation
3. `test_minimum_explanations`: ≥3 explanations
4. `test_deterministic_results`: Same input → same output

**Why**: These are non-negotiable requirements. If any fail, system is broken.

### Integration Tests

**File**: `backend/tests/test_api.py`

**Tests**:
- API endpoints return correct structure
- Audit logs are created
- Validation rejects invalid input
- Determinism holds at API level

### Connector Tests

**File**: `backend/tests/test_connectors.py`

**Tests**:
- Health checks work
- Normalization produces valid CanonicalLoad
- Location-based filtering works

## Future Enhancements

### Near-Term (Next Sprint)

1. **Real Truckstop API Integration**
   - Replace mock JSON with live API calls
   - Add rate limiting and error handling

2. **User Accounts**
   - Save truck profiles
   - Track optimization history
   - Preferred lanes / home markets

3. **Enhanced Forward Look**
   - Weather integration (critical for reefer)
   - Traffic/route optimization
   - Fuel stop planning

### Medium-Term (Q2)

1. **ML-Based Reload Scoring**
   - Train on historical data
   - Market seasonality patterns
   - Time-series forecasting

2. **Multi-Stop Optimization**
   - Find 2-3 load sequences
   - Maximize revenue over 24-48 hours

3. **Mobile Native App**
   - Offline mode for dead zones
   - Push notifications for new loads
   - GPS auto-location

### Long-Term (Q3+)

1. **Fleet Management**
   - Multi-truck optimization
   - Dispatcher dashboard

2. **Market Intelligence**
   - Rate trends by lane
   - Demand forecasting
   - Capacity insights

## Performance Considerations

### Current Performance

- **Optimization**: <1 second for 25 loads
- **API Response**: <200ms average
- **Frontend Load**: <2 seconds on 4G

### Scaling Concerns

**If load count grows to 1000+**:
- Add parallel connector fetching
- Cache normalized loads (Redis)
- Pre-filter by equipment type before fetching

**If request volume grows to 100+ req/sec**:
- Add API rate limiting
- Horizontal scaling (multiple FastAPI instances)
- Read replica for audit logs

## Security Considerations

- **API Authentication**: Not implemented in MVP (add OAuth2 for production)
- **Rate Limiting**: Not implemented (add for production)
- **Input Validation**: Pydantic models enforce types/bounds
- **SQL Injection**: Using SQLAlchemy ORM (safe)
- **CORS**: Configured for localhost (update for production)

## Deployment Architecture (Production)

```
                  Internet
                     │
                     ▼
              ┌─────────────┐
              │   CDN       │ (Frontend static files)
              └─────────────┘
                     │
                     ▼
              ┌─────────────┐
              │  Load       │
              │  Balancer   │
              └─────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
    ┌──────────┐          ┌──────────┐
    │ FastAPI  │          │ FastAPI  │  (Auto-scaled)
    │ Instance │          │ Instance │
    └──────────┘          └──────────┘
          │                     │
          └──────────┬──────────┘
                     ▼
              ┌─────────────┐
              │ PostgreSQL  │  (Managed RDS)
              │  Primary    │
              └─────────────┘
                     │
                     ▼
              ┌─────────────┐
              │ PostgreSQL  │  (Read Replica)
              │  Replica    │  (For audit log queries)
              └─────────────┘
```

---

**Philosophy**: This is decision intelligence for stressed humans. Every design choice prioritizes clarity, safety, and explainability over complexity or features.
