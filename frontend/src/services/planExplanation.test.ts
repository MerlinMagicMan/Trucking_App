/**
 * Vitest tests for planExplanation.ts (NEXT-002 v1.1)
 */

import { describe, it, expect } from 'vitest';
import { generatePlanExplanation } from './planExplanation';
import type { Plan, RankingBreakdown, RankingAvailability } from '../types/plan';

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
    time_blocks: [],
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

function makeBreakdown(overrides: Partial<RankingBreakdown> = {}): RankingBreakdown {
  const availability: RankingAvailability = {
    has_confidence_score: false,
    reload_bonus_available: false,
    dwell_penalty_available: false,
    ...(overrides.availability || {}),
  };
  return {
    profit_per_day_cents: 42050,
    base_profit_score: 80,
    confidence_multiplier: 1.0,
    deadhead_penalty: 2,
    reload_bonus: 0,
    dwell_penalty: 0,
    final_score: 78,
    ...overrides,
    availability,
  };
}

// ---- Core constraints ----

describe('generatePlanExplanation', () => {
  it('generates explanation ≤90 characters for rank 1', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown();
    const result = generatePlanExplanation(plan, breakdown, 1);
    expect(result.length).toBeLessThanOrEqual(90);
  });

  it('generates explanation ≤90 characters for rank 2', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown();
    const result = generatePlanExplanation(plan, breakdown, 2);
    expect(result.length).toBeLessThanOrEqual(90);
  });

  it('generates explanation ≤90 characters for rank 3+', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown();
    const result = generatePlanExplanation(plan, breakdown, 3);
    expect(result.length).toBeLessThanOrEqual(90);
  });

  it('uses whole dollar formatting (no cents)', () => {
    const plan = makePlan({ profit_per_day_usd: 420.99 });
    const breakdown = makeBreakdown({ profit_per_day_cents: 42099 });
    const result = generatePlanExplanation(plan, breakdown, 1);
    // Should contain "$421" (rounded), NOT "$420.99"
    expect(result).toMatch(/\$\d+/);
    expect(result).not.toMatch(/\$\d+\.\d+/);
  });

  it('is deterministic: same inputs produce same output', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown();
    const r1 = generatePlanExplanation(plan, breakdown, 1);
    const r2 = generatePlanExplanation(plan, breakdown, 1);
    expect(r1).toBe(r2);
  });

  it('returns non-empty string', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown();
    const result = generatePlanExplanation(plan, breakdown, 1);
    expect(result.length).toBeGreaterThan(0);
  });
});

// ---- Rank-specific behavior ----

describe('rank 1 explanations', () => {
  it('mentions deadhead when penalty is high', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown({ deadhead_penalty: 8 });
    const result = generatePlanExplanation(plan, breakdown, 1);
    expect(result.toLowerCase()).toContain('deadhead');
  });

  it('mentions wait time when dwell penalty is high', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown({ deadhead_penalty: 0, dwell_penalty: 5 });
    const result = generatePlanExplanation(plan, breakdown, 1);
    expect(result.toLowerCase()).toContain('wait');
  });

  it('mentions reload market when bonus is present', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown({
      deadhead_penalty: 0,
      dwell_penalty: 0,
      reload_bonus: 10,
      availability: {
        has_confidence_score: false,
        reload_bonus_available: true,
        dwell_penalty_available: false,
      },
    });
    const result = generatePlanExplanation(plan, breakdown, 1);
    expect(result.toLowerCase()).toContain('reload');
  });
});

describe('rank 2 explanations', () => {
  it('mentions low deadhead when applicable', () => {
    const plan = makePlan({
      loads: [{
        load: {
          id: 'l1', source: 'dat', external_id: 'e1', posted_at: '2025-01-01T00:00:00Z',
          equipment: 'dry_van',
          pickup: { city: 'A', state: 'OK', lat: 35, lng: -97 },
          delivery: { city: 'B', state: 'TX', lat: 33, lng: -96 },
          rate_total: 2000, miles: 200,
        },
        sequence_number: 1, deadhead_miles: 10,
        revenue_usd: 2000, estimated_fuel_cost_usd: 100, estimated_toll_cost_usd: 10,
        net_revenue_usd: 1890, time_blocks: [],
      }],
    });
    const breakdown = makeBreakdown({ deadhead_penalty: 0 });
    const result = generatePlanExplanation(plan, breakdown, 2);
    expect(result.toLowerCase()).toContain('deadhead');
  });

  it('mentions high confidence when applicable', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown({ deadhead_penalty: 5, confidence_multiplier: 0.98 });
    const result = generatePlanExplanation(plan, breakdown, 2);
    expect(result.toLowerCase()).toContain('confidence');
  });
});

describe('rank 3+ explanations', () => {
  it('mentions minimal deadhead when no penalty', () => {
    const plan = makePlan();
    const breakdown = makeBreakdown({ deadhead_penalty: 0 });
    const result = generatePlanExplanation(plan, breakdown, 3);
    expect(result.toLowerCase()).toContain('deadhead');
  });

  it('mentions low risk when no high-severity signals', () => {
    const plan = makePlan({ risk_signals: [] });
    const breakdown = makeBreakdown({ deadhead_penalty: 5 });
    const result = generatePlanExplanation(plan, breakdown, 4);
    expect(result.toLowerCase()).toContain('low-risk');
  });

  it('falls back to generic when deadhead exists and has risk signals', () => {
    const plan = makePlan({
      risk_signals: [
        { timestamp: '2025-01-01T00:00:00Z', risk_type: 'weather', severity: 'medium', description: 'Storm', impact_score: 50 },
      ],
    });
    const breakdown = makeBreakdown({ deadhead_penalty: 5 });
    const result = generatePlanExplanation(plan, breakdown, 5);
    expect(result).toContain('Alternative');
  });
});

// ---- Edge cases ----

describe('edge cases', () => {
  it('handles 0 cents gracefully', () => {
    const plan = makePlan({ profit_per_day_usd: 0 });
    const breakdown = makeBreakdown({ profit_per_day_cents: 0 });
    const result = generatePlanExplanation(plan, breakdown, 1);
    expect(result.length).toBeLessThanOrEqual(90);
    expect(result).toContain('$0');
  });

  it('handles very large cent values', () => {
    const plan = makePlan({ profit_per_day_usd: 99999 });
    const breakdown = makeBreakdown({ profit_per_day_cents: 9999900 });
    const result = generatePlanExplanation(plan, breakdown, 1);
    expect(result.length).toBeLessThanOrEqual(90);
  });
});
