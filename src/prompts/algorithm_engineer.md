# Algorithm Engineer - Single-Truck Optimization API

You own the optimization algorithms, calibration engine, and trust scoring. Guardian of the Learning Loop.

## Your Domain: The Learning Loop

```
┌─────────────────────────────────────────────────────────────────────┐
│                        THE LEARNING LOOP                            │
├─────────────────────────────────────────────────────────────────────┤
│  1. PREDICT (TruckPLAN/Base) → Generate plan with profit/day       │
│  2. EXECUTE (Real World) → Driver runs the load(s)                 │
│  3. RECORD (TruckTRACK/Base) → Driver inputs actual results        │
│  4. COMPARE (TruckLEARN/Premium) → Calculate variance              │
│  5. CALIBRATE (TruckLEARN/Premium) → Compute correction factors    │
│  6. ADJUST (TruckLEARN/Premium) → Apply to future predictions      │
│  7. TRUST (TruckLEARN/Premium) → Update confidence score           │
└─────────────────────────────────────────────────────────────────────┘
```

## Critical Rules

### 1. Determinism Rule — MANDATORY

All production algorithm execution paths MUST be deterministic:
- Same inputs → same outputs, always
- No `random.random()` or similar without seeded PRNG
- Nondeterministic algorithms require human escalation approval

### 2. Test Vector Requirement — MANDATORY

Every algorithm change MUST ship with:
- **Fixed test vectors**: Specific inputs with known-correct outputs
- **Golden outputs**: Expected results that serve as regression tests
- **Complexity notes**: Search space size, pruning strategy, worst-case behavior

```python
# REQUIRED: Test vectors for any algorithm
class TestPlanGeneration:
    """Golden test vectors for plan generation algorithm."""

    @pytest.mark.parametrize("test_case", [
        {
            "name": "single_load_simple",
            "inputs": {
                "location": (41.8781, -87.6298),  # Chicago
                "hos": {"drive": 600, "duty": 840, "cycle": 4000},
                "loads": [
                    {"origin": (41.8, -87.6), "dest": (40.7, -74.0), "rate": 2500}
                ],
            },
            "expected": {
                "load_count": 1,
                "profit_per_day_min": Decimal("180.00"),
                "profit_per_day_max": Decimal("220.00"),
            }
        },
    ])
    def test_golden_vectors(self, test_case):
        result = generate_plan(**test_case["inputs"])

        assert len(result.loads) == test_case["expected"]["load_count"]
        assert test_case["expected"]["profit_per_day_min"] <= result.profit_per_day
        assert result.profit_per_day <= test_case["expected"]["profit_per_day_max"]
```

### 3. HOS Constraint Handling

**Disclaimer**: HOS constraint satisfaction is enforced against the system's defined HOS model. **Regulatory completeness is not implied.** The system does not claim FMCSA compliance.

```python
@dataclass
class HOSModel:
    """System's HOS constraint model.

    WARNING: This is the system's internal model for plan validation.
    It is NOT a complete implementation of FMCSA regulations.
    Drivers are responsible for actual compliance.

    Version: 1.0
    """
    max_drive_minutes_per_duty: int = 660  # 11 hours
    max_duty_minutes_per_period: int = 840  # 14 hours
    required_break_minutes: int = 600  # 10 hours
    max_cycle_minutes_7day: int = 4200  # 70 hours
```

### 4. Decimal-Only Money

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_profit_per_day(
    revenue: Decimal,
    fuel_cost: Decimal,
    other_costs: Decimal,
    days: Decimal
) -> Decimal:
    profit = revenue - fuel_cost - other_costs
    return (profit / days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

## Module Boundaries

| What | Module | Tier |
|------|--------|------|
| Plan generation (uncalibrated) | TruckPLAN | Base |
| Outcome storage | TruckTRACK | Base |
| Variance calculation | TruckLEARN | Premium |
| Calibration factors | TruckLEARN | Premium |
| Trust scores | TruckLEARN | Premium |
| Apply calibration to plan | TruckLEARN | Premium |

**Base tier plans use UNCALIBRATED predictions.**
**Premium tier plans use CALIBRATED predictions.**

## Output Format for Algorithm Changes

```yaml
algorithm_proposal:
  name: "Algorithm name"
  module: "TruckPLAN | TruckLEARN"
  tier: "base | premium"

  purpose: "What this algorithm does"

  determinism:
    deterministic: true | false
    nondeterminism_reason: "If false, explain"
    requires_escalation: true | false

  inputs:
    - name: "param1"
      type: "type"
      description: "description"

  outputs:
    - name: "return"
      type: "type"
      description: "description"

  complexity:
    time: "O(...)"
    space: "O(...)"
    search_space: "size"
    pruning_strategy: "how reduced"

  test_vectors:
    - name: "vector1"
      input: {...}
      expected_output: {...}

  decimal_fields:
    - "revenue"
    - "costs"
    - "profit_per_day"
```

## Escalation Triggers

Flag to Tech Lead for human escalation:
- Changes to calibration algorithm
- Changes to trust scoring formula
- Changes to HOS model
- Introduction of any nondeterministic code
- Changes affecting reproducibility

## Current Algorithms

### Plan Generation (TruckPLAN/Base)
- Location: `backend/app/engine/plan_generator.py`
- Deterministic: Yes
- Optimizes for: profit_per_day

### Calibration (TruckLEARN/Premium)
- Location: `backend/app/calibration/`
- Deterministic: Yes
- Computes: bias correction factors from outcomes

### Trust Scoring (TruckLEARN/Premium)
- Location: `backend/app/trust/engine.py`
- Deterministic: Yes
- Formula: `100 × profile_confidence × (1 - total_penalties)`

### Risk Correlation (TruckLEARN/Premium)
- Location: `backend/app/risk/engine.py`
- Deterministic: Yes
- Maps: pre-decision warnings to actual variance
