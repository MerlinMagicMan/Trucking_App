/**
 * Vitest tests for planRanking.ts (NEXT-002 v1.1)
 */

import { describe, it, expect } from 'vitest';
import {
  parseUsdToCents,
  computeBaseProfit,
  computeConfidenceMultiplier,
  computeDeadheadPenalty,
  computeReloadBonus,
  computeDwellPenalty,
  computeRankingBreakdown,
  rankPlans,
  SCORING_CONSTANTS,
} from './planRanking';
import type { Plan } from '../types/plan';

// ---- Helpers ----

function makePlan(overrides: Partial<Plan> = {}): Plan {
  return {
    plan_id: 'test-plan-1',
    created_at: '2025-01-01T00:00:00Z',
    truck_snapshot: { current_lat: 35, current_lng: -97, hos: { drive_remaining_min: 660, on_duty_remaining_min: 840, cycle_remaining_min: 4200 } },
    planning_horizon_days: 7,
    loads: [
      {
        load: {
          id: 'load-1', source: 'dat', external_id: 'ext-1', posted_at: '2025-01-01T00:00:00Z',
          equipment: 'dry_van',
          pickup: { city: 'OKC', state: 'OK', lat: 35.4, lng: -97.5 },
          delivery: { city: 'Dallas', state: 'TX', lat: 32.7, lng: -96.8 },
          rate_total: 2500, miles: 200,
        },
        sequence_number: 1,
        deadhead_miles: 30,
        revenue_usd: 2500,
        estimated_fuel_cost_usd: 150,
        estimated_toll_cost_usd: 20,
        net_revenue_usd: 2330,
        time_blocks: [],
      },
    ],
    time_blocks: [
      { start_time: '2025-01-01T06:00:00Z', end_time: '2025-01-01T10:00:00Z', duration_min: 240, block_type: 'drive_loaded' },
    ],
    end_location_lat: 32.7,
    end_location_lng: -96.8,
    end_location_name: 'Dallas, TX',
    total_revenue_usd: 2500,
    total_costs_usd: 170,
    net_profit_usd: 2330,
    profit_per_day_usd: 420.50,
    financial_events: [],
    risk_signals: [],
    maintenance_events: [],
    plan_score: 80,
    confidence: 'high',
    explanations: ['Good route', 'Low deadhead', 'Strong market'],
    warnings: [],
    loads_analyzed: 10,
    plans_generated: 3,
    ...overrides,
  };
}

// ---- parseUsdToCents ----

describe('parseUsdToCents', () => {
  it('converts whole dollars', () => {
    expect(parseUsdToCents(420)).toBe(42000);
  });

  it('converts dollars with cents', () => {
    expect(parseUsdToCents(420.50)).toBe(42050);
  });

  it('converts single cent', () => {
    expect(parseUsdToCents(420.5)).toBe(42050);
  });

  it('handles zero', () => {
    expect(parseUsdToCents(0)).toBe(0);
  });

  it('handles negative values', () => {
    expect(parseUsdToCents(-50.25)).toBe(-5025);
  });

  it('is string-safe: avoids float precision issues', () => {
    // 0.1 + 0.2 = 0.30000000000000004 in float
    // But parseUsdToCents(0.30) should be 30, not 30.000000000000004
    expect(parseUsdToCents(0.30)).toBe(30);
  });

  it('truncates beyond 2 decimal places', () => {
    expect(parseUsdToCents(1.999)).toBe(199);
  });
});

// ---- computeBaseProfit ----

describe('computeBaseProfit', () => {
  it('returns 50 when max === min (single plan or identical profits)', () => {
    expect(computeBaseProfit(42000, 42000, 42000)).toBe(50);
  });

  it('returns 100 for the highest profit plan', () => {
    expect(computeBaseProfit(50000, 30000, 50000)).toBe(100);
  });

  it('returns 0 for the lowest profit plan', () => {
    expect(computeBaseProfit(30000, 30000, 50000)).toBe(0);
  });

  it('returns midpoint for average plan', () => {
    expect(computeBaseProfit(40000, 30000, 50000)).toBe(50);
  });

  it('clamps to 0-100 range', () => {
    // Below min shouldn't happen, but clamped
    expect(computeBaseProfit(20000, 30000, 50000)).toBe(0);
  });
});

// ---- computeConfidenceMultiplier ----

describe('computeConfidenceMultiplier', () => {
  it('returns 1.0 for high confidence string label', () => {
    const plan = makePlan({ confidence: 'high' });
    const result = computeConfidenceMultiplier(plan);
    expect(result.value).toBe(1.0);
    expect(result.hasNumericScore).toBe(false);
  });

  it('returns 0.85 for medium confidence string label', () => {
    const plan = makePlan({ confidence: 'medium' });
    const result = computeConfidenceMultiplier(plan);
    expect(result.value).toBe(0.85);
    expect(result.hasNumericScore).toBe(false);
  });

  it('returns 0.7 for low confidence string label', () => {
    const plan = makePlan({ confidence: 'low' });
    const result = computeConfidenceMultiplier(plan);
    expect(result.value).toBe(0.7);
    expect(result.hasNumericScore).toBe(false);
  });

  it('uses numeric confidence_score when present', () => {
    const plan = makePlan({ confidence_score: 80 });
    const result = computeConfidenceMultiplier(plan);
    expect(result.hasNumericScore).toBe(true);
    // 0.7 + (80/100) * 0.3 = 0.7 + 0.24 = 0.94
    expect(result.value).toBe(0.94);
  });

  it('clamps confidence_score to 0-100', () => {
    const plan = makePlan({ confidence_score: 150 });
    const result = computeConfidenceMultiplier(plan);
    expect(result.value).toBe(1.0);
  });

  it('has_confidence_score availability flag', () => {
    const withScore = makePlan({ confidence_score: 50 });
    const withoutScore = makePlan({ confidence_score: null });
    expect(computeConfidenceMultiplier(withScore).hasNumericScore).toBe(true);
    expect(computeConfidenceMultiplier(withoutScore).hasNumericScore).toBe(false);
  });
});

// ---- computeDeadheadPenalty ----

describe('computeDeadheadPenalty', () => {
  it('returns 0 when deadhead is below threshold', () => {
    const plan = makePlan(); // 30 / 230 = ~13% < 15%
    expect(computeDeadheadPenalty(plan)).toBe(0);
  });

  it('returns penalty when deadhead exceeds threshold', () => {
    const plan = makePlan({
      loads: [{
        load: {
          id: 'l1', source: 'dat', external_id: 'e1', posted_at: '2025-01-01T00:00:00Z',
          equipment: 'dry_van',
          pickup: { city: 'A', state: 'OK', lat: 35, lng: -97 },
          delivery: { city: 'B', state: 'TX', lat: 33, lng: -96 },
          rate_total: 2000, miles: 100,
        },
        sequence_number: 1, deadhead_miles: 100,
        revenue_usd: 2000, estimated_fuel_cost_usd: 100, estimated_toll_cost_usd: 10,
        net_revenue_usd: 1890, time_blocks: [],
      }],
    }); // 100 / 200 = 50% deadhead, excess = 35%, penalty = 35 * 0.5 = 17.5 → capped at 15
    expect(computeDeadheadPenalty(plan)).toBe(SCORING_CONSTANTS.DEADHEAD_MAX_PENALTY);
  });

  it('returns 0 when totalMiles is 0', () => {
    const plan = makePlan({
      loads: [{
        load: {
          id: 'l1', source: 'dat', external_id: 'e1', posted_at: '2025-01-01T00:00:00Z',
          equipment: 'dry_van',
          pickup: { city: 'A', state: 'OK', lat: 35, lng: -97 },
          delivery: { city: 'B', state: 'TX', lat: 33, lng: -96 },
          rate_total: 2000,
        },
        sequence_number: 1, deadhead_miles: 0,
        revenue_usd: 2000, estimated_fuel_cost_usd: 0, estimated_toll_cost_usd: 0,
        net_revenue_usd: 2000, time_blocks: [],
      }],
    });
    expect(computeDeadheadPenalty(plan)).toBe(0);
  });
});

// ---- computeReloadBonus ----

describe('computeReloadBonus', () => {
  it('returns 0 with available=false when no market data', () => {
    const result = computeReloadBonus(null);
    expect(result.value).toBe(0);
    expect(result.available).toBe(false);
  });

  it('returns 0 with available=false when undefined', () => {
    const result = computeReloadBonus(undefined);
    expect(result.value).toBe(0);
    expect(result.available).toBe(false);
  });

  it('returns hot bonus for hot market', () => {
    const result = computeReloadBonus('hot');
    expect(result.value).toBe(SCORING_CONSTANTS.RELOAD_BONUS_HOT);
    expect(result.available).toBe(true);
  });

  it('returns hot bonus for warm market', () => {
    const result = computeReloadBonus('warm');
    expect(result.value).toBe(SCORING_CONSTANTS.RELOAD_BONUS_HOT);
    expect(result.available).toBe(true);
  });

  it('returns neutral bonus for neutral market', () => {
    const result = computeReloadBonus('neutral');
    expect(result.value).toBe(SCORING_CONSTANTS.RELOAD_BONUS_NEUTRAL);
    expect(result.available).toBe(true);
  });

  it('returns 0 with available=true for cold market', () => {
    const result = computeReloadBonus('cold');
    expect(result.value).toBe(0);
    expect(result.available).toBe(true);
  });
});

// ---- computeDwellPenalty ----

describe('computeDwellPenalty', () => {
  it('returns available=false when no waiting blocks', () => {
    const plan = makePlan({ time_blocks: [
      { start_time: '2025-01-01T06:00:00Z', end_time: '2025-01-01T10:00:00Z', duration_min: 240, block_type: 'drive_loaded' },
    ]});
    const result = computeDwellPenalty(plan);
    expect(result.value).toBe(0);
    expect(result.available).toBe(false);
  });

  it('returns 0 penalty when wait is below threshold', () => {
    const plan = makePlan({ time_blocks: [
      { start_time: '2025-01-01T06:00:00Z', end_time: '2025-01-01T08:00:00Z', duration_min: 120, block_type: 'waiting' },
    ]});
    const result = computeDwellPenalty(plan);
    expect(result.value).toBe(0);
    expect(result.available).toBe(true);
  });

  it('returns penalty when wait exceeds threshold', () => {
    const plan = makePlan({ time_blocks: [
      { start_time: '2025-01-01T06:00:00Z', end_time: '2025-01-01T16:00:00Z', duration_min: 600, block_type: 'waiting' },
    ]});
    // 600 - 240 = 360 min excess = 6 hours * 3 = 18 → capped at 10
    const result = computeDwellPenalty(plan);
    expect(result.value).toBe(SCORING_CONSTANTS.DWELL_MAX_PENALTY);
    expect(result.available).toBe(true);
  });
});

// ---- computeRankingBreakdown ----

describe('computeRankingBreakdown', () => {
  it('produces a complete breakdown with all fields', () => {
    const plan = makePlan();
    const breakdown = computeRankingBreakdown(plan, 30000, 50000);
    expect(breakdown).toHaveProperty('profit_per_day_cents');
    expect(breakdown).toHaveProperty('base_profit_score');
    expect(breakdown).toHaveProperty('confidence_multiplier');
    expect(breakdown).toHaveProperty('deadhead_penalty');
    expect(breakdown).toHaveProperty('reload_bonus');
    expect(breakdown).toHaveProperty('dwell_penalty');
    expect(breakdown).toHaveProperty('final_score');
    expect(breakdown).toHaveProperty('availability');
    expect(breakdown.availability).toHaveProperty('has_confidence_score');
    expect(breakdown.availability).toHaveProperty('reload_bonus_available');
    expect(breakdown.availability).toHaveProperty('dwell_penalty_available');
  });

  it('uses profit_per_day_cents when already on plan', () => {
    const plan = makePlan({ profit_per_day_cents: 42050 });
    const breakdown = computeRankingBreakdown(plan, 30000, 50000);
    expect(breakdown.profit_per_day_cents).toBe(42050);
  });

  it('falls back to parseUsdToCents when profit_per_day_cents is missing', () => {
    const plan = makePlan({ profit_per_day_usd: 420.50 });
    const breakdown = computeRankingBreakdown(plan, 30000, 50000);
    expect(breakdown.profit_per_day_cents).toBe(42050);
  });

  it('final_score is clamped to 0-100', () => {
    const plan = makePlan();
    const breakdown = computeRankingBreakdown(plan, 30000, 50000);
    expect(breakdown.final_score).toBeGreaterThanOrEqual(0);
    expect(breakdown.final_score).toBeLessThanOrEqual(100);
  });

  it('marks reload_bonus_available=false when no market temperature', () => {
    const plan = makePlan();
    const breakdown = computeRankingBreakdown(plan, 30000, 50000);
    expect(breakdown.availability.reload_bonus_available).toBe(false);
    expect(breakdown.reload_bonus).toBe(0);
  });

  it('marks reload_bonus_available=true when market temperature provided', () => {
    const plan = makePlan();
    const breakdown = computeRankingBreakdown(plan, 30000, 50000, 'hot');
    expect(breakdown.availability.reload_bonus_available).toBe(true);
    expect(breakdown.reload_bonus).toBe(10);
  });
});

// ---- rankPlans ----

describe('rankPlans', () => {
  it('returns empty array for empty input', () => {
    expect(rankPlans([])).toEqual([]);
  });

  it('sorts plans by final_score descending', () => {
    const plans = [
      makePlan({ plan_id: 'low', profit_per_day_usd: 200 }),
      makePlan({ plan_id: 'high', profit_per_day_usd: 600 }),
      makePlan({ plan_id: 'mid', profit_per_day_usd: 400 }),
    ];
    const ranked = rankPlans(plans);
    expect(ranked[0].plan_id).toBe('high');
    expect(ranked[2].plan_id).toBe('low');
  });

  it('attaches ranking_breakdown to each plan', () => {
    const plans = [makePlan(), makePlan({ plan_id: 'p2', profit_per_day_usd: 300 })];
    const ranked = rankPlans(plans);
    for (const p of ranked) {
      expect(p.ranking_breakdown).toBeDefined();
      expect(p.profit_per_day_cents).toBeDefined();
    }
  });

  it('does not mutate the original array', () => {
    const plans = [makePlan({ plan_id: 'a' }), makePlan({ plan_id: 'b' })];
    const original = [...plans];
    rankPlans(plans);
    expect(plans[0].plan_id).toBe(original[0].plan_id);
    expect(plans[1].plan_id).toBe(original[1].plan_id);
  });

  it('single plan gets base_profit_score = 50', () => {
    const plans = [makePlan()];
    const ranked = rankPlans(plans);
    expect(ranked[0].ranking_breakdown!.base_profit_score).toBe(50);
  });

  it('is deterministic: same inputs produce same outputs', () => {
    const plans = [
      makePlan({ plan_id: 'a', profit_per_day_usd: 500 }),
      makePlan({ plan_id: 'b', profit_per_day_usd: 300 }),
      makePlan({ plan_id: 'c', profit_per_day_usd: 400 }),
    ];
    const run1 = rankPlans(plans);
    const run2 = rankPlans(plans);
    expect(run1.map(p => p.plan_id)).toEqual(run2.map(p => p.plan_id));
    for (let i = 0; i < run1.length; i++) {
      expect(run1[i].ranking_breakdown).toEqual(run2[i].ranking_breakdown);
    }
  });
});
