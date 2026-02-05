# Schema Constitution - Single-Truck Optimization API

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-02-05 | Initial constitution |

---

## Inviolable Rules

These rules CANNOT be violated. Any violation requires human escalation.

### RULE-001: Decimal-Only Money

**All monetary columns MUST use Numeric/Decimal, never Float.**

```python
# CORRECT
revenue = Column(Numeric(12, 2), nullable=False)
costs = Column(Numeric(12, 2), nullable=False)

# WRONG - CONSTITUTION VIOLATION
revenue = Column(Float)  # ❌ BANNED
```

**Rationale**: Floating point errors in profit calculations destroy trust in the system.

**Enforcement**: Schema review, type checking, QA blocking.

---

### RULE-002: Org-Scoped Business Tables

**All business tables MUST have an org_id column.**

```python
# CORRECT
class PlanGenerationEvent(Base):
    org_id = Column(UUID, ForeignKey("organizations.id"), nullable=False, index=True)

# WRONG - CONSTITUTION VIOLATION
class PlanGenerationEvent(Base):
    # Missing org_id ❌ BANNED
```

**Rationale**: Multi-tenant security requires org isolation at the data level.

**Exceptions**: Only the `organizations` table itself is exempt.

**Enforcement**: Schema review, Database Architect approval.

---

### RULE-003: Timestamp Columns

**All tables MUST have created_at and updated_at columns.**

```python
# CORRECT
class AnyTable(Base):
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

**Rationale**: Audit trail and debugging require timestamp tracking.

**Enforcement**: Schema review, SQLAlchemy event listeners.

---

### RULE-004: Outcome Append-Only

**Outcome tables are append-only. No UPDATE or DELETE.**

```python
# Tables covered by this rule:
# - plan_outcomes
# - plan_prediction_snapshots
# - decision_context_snapshots
# - decision_events
```

**Rationale**: Learning loop integrity requires immutable historical data.

**Enforcement**: Application layer (no update/delete methods), QA blocking.

---

### RULE-005: Schema Authority

**Only Database Architect may name new tables/columns.**

Other agents may NOT:
- Invent table names
- Assume column names
- Reference non-existent schema

**Process**:
1. Agent flags schema need to Tech Lead
2. Database Architect proposes via Alembic
3. Tech Lead approves
4. Migration created and tested
5. Only then proceed with implementation

**Enforcement**: Agent rules, code review.

---

## Module Ownership

Tables are owned by specific modules. Cross-module access requires explicit review.

### TruckCORE (Base)
- `organizations`
- `trucks`

### TruckPLAN (Base)
- `plan_generation_events`

### TruckTRACK (Base)
- `plan_prediction_snapshots`
- `plan_outcomes`
- `decision_events`

### TruckLEARN (Premium)
- `decision_context_snapshots`

### TruckINSIGHT (Premium)
- `lane_statistics`
- `market_statistics`
- `destination_scores`

### TruckCONNECT (Premium)
- `load_snapshots`

### TruckFLEET (Enterprise)
- (No tables yet)

---

## Evolution Boundaries

### Safe Changes (No Approval Required)
- Adding nullable columns
- Adding new tables following constitution
- Adding indexes

### Requires Review (Database Architect + Tech Lead)
- Modifying column types
- Adding NOT NULL to existing columns
- Changes to calibration/trust tables
- Foreign key changes

### Forbidden (Human Escalation Required)
- Float for monetary values
- Removing org_id from business tables
- Modifying outcomes after creation
- Deleting calibration/trust history
- Removing timestamp columns

---

## Current Schema Inventory

### organizations
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    tier VARCHAR NOT NULL DEFAULT 'base',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### trucks
```sql
CREATE TABLE trucks (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR NOT NULL,
    current_lat NUMERIC(9,6),
    current_lon NUMERIC(9,6),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### plan_generation_events
```sql
CREATE TABLE plan_generation_events (
    id SERIAL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    snapshot_id UUID NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    planning_horizon_days INTEGER NOT NULL,
    plans_generated INTEGER NOT NULL,
    loads_analyzed INTEGER,
    execution_time_ms INTEGER,
    full_payload JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### plan_prediction_snapshots
```sql
CREATE TABLE plan_prediction_snapshots (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    plan_id VARCHAR NOT NULL,
    decision_event_id INTEGER REFERENCES decision_events(id),
    captured_at TIMESTAMP NOT NULL,
    predicted_revenue NUMERIC(12,2) NOT NULL,
    predicted_costs NUMERIC(12,2) NOT NULL,
    predicted_net_profit NUMERIC(12,2) NOT NULL,
    predicted_miles_total INTEGER,
    predicted_miles_deadhead INTEGER,
    predicted_duration_min INTEGER,
    load_ids JSONB,
    plan_metadata JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### plan_outcomes
```sql
CREATE TABLE plan_outcomes (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    plan_id VARCHAR NOT NULL,
    snapshot_id UUID REFERENCES plan_prediction_snapshots(id),
    status VARCHAR NOT NULL DEFAULT 'pending',
    source VARCHAR NOT NULL DEFAULT 'system',
    actual_revenue NUMERIC(12,2),
    actual_fuel_spend NUMERIC(12,2),
    actual_tolls NUMERIC(12,2),
    actual_maintenance NUMERIC(12,2),
    actual_other_costs NUMERIC(12,2),
    actual_miles_loaded INTEGER,
    actual_miles_deadhead INTEGER,
    actual_drive_min INTEGER,
    actual_wait_min INTEGER,
    notes TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### decision_events
```sql
CREATE TABLE decision_events (
    id SERIAL PRIMARY KEY,
    org_id UUID NOT NULL,
    plan_id VARCHAR NOT NULL,
    decision_type VARCHAR NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP NOT NULL,
    snapshot_id UUID,
    outcome_id UUID,
    decision_context_snapshot_id UUID,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### decision_context_snapshots
```sql
CREATE TABLE decision_context_snapshots (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    plan_id VARCHAR NOT NULL,
    decision_event_id INTEGER REFERENCES decision_events(id),
    captured_at TIMESTAMP NOT NULL,
    trust_confidence_score INTEGER,
    trust_confidence_label VARCHAR(20),
    trust_warnings JSONB,
    copilot_status VARCHAR(20),
    copilot_signals JSONB,
    calibration_accuracy_score VARCHAR(10),
    calibration_sample_size INTEGER,
    plan_predicted_revenue VARCHAR(20),
    plan_predicted_costs VARCHAR(20),
    plan_predicted_net_profit VARCHAR(20),
    plan_profit_per_day VARCHAR(20),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

## Amendment Process

1. Propose amendment with rationale
2. Database Architect review
3. Tech Lead approval
4. Human developer sign-off
5. Update constitution document
6. Announce to team

**Constitution amendments require human approval.**
