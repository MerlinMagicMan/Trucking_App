/**
 * Plan Ranking Engine (NEXT-002 v1.1)
 *
 * Pure, deterministic functions for multi-factor plan scoring.
 * All money math uses integer cents. Normalization is within-batch.
 * Missing data falls back to 0 with availability flags.
 */

import type { Plan, RankingBreakdown, RankingAvailability } from '../types/plan';

// ---- Scoring Constants ----

export const SCORING_CONSTANTS = {
  /** Floor for confidence multiplier (lowest possible value) */
  CONFIDENCE_FLOOR: 0.7,
  /** Deadhead % above this threshold incurs penalty */
  DEADHEAD_THRESHOLD_PCT: 15,
  /** Maximum penalty for deadhead (points subtracted) */
  DEADHEAD_MAX_PENALTY: 15,
  /** Bonus points for hot reload market at destination */
  RELOAD_BONUS_HOT: 10,
  /** Bonus points for neutral reload market at destination */
  RELOAD_BONUS_NEUTRAL: 5,
  /** Wait time above this threshold (minutes) incurs penalty */
  DWELL_THRESHOLD_MIN: 240,
  /** Maximum penalty for excessive dwell time */
  DWELL_MAX_PENALTY: 10,
} as const;

// ---- Cents Conversion ----

/**
 * Convert a USD number to integer cents.
 * String-safe: converts to string first to avoid float precision issues.
 */
export function parseUsdToCents(usd: number): number {
  const str = String(usd);
  const parts = str.split('.');
  const whole = parseInt(parts[0], 10) || 0;
  let frac = 0;
  if (parts[1] !== undefined) {
    // Pad or truncate to 2 decimal places
    const fracStr = (parts[1] + '00').slice(0, 2);
    frac = parseInt(fracStr, 10) || 0;
  }
  return whole * 100 + (usd < 0 ? -frac : frac);
}

// ---- Individual Scoring Functions ----

/**
 * Base profit score: within-batch normalized to 0-100.
 * If max === min (single plan or identical profits), score = 50.
 */
export function computeBaseProfit(
  planCents: number,
  batchMinCents: number,
  batchMaxCents: number,
): number {
  if (batchMaxCents === batchMinCents) return 50;
  const raw = ((planCents - batchMinCents) / (batchMaxCents - batchMinCents)) * 100;
  return Math.round(Math.max(0, Math.min(100, raw)));
}

/**
 * Confidence multiplier: 0.7-1.0.
 * Uses numeric confidence_score when present; falls back to string label.
 */
export function computeConfidenceMultiplier(plan: Plan): {
  value: number;
  hasNumericScore: boolean;
} {
  if (plan.confidence_score != null) {
    const clamped = Math.max(0, Math.min(100, plan.confidence_score));
    const multiplier = SCORING_CONSTANTS.CONFIDENCE_FLOOR +
      (clamped / 100) * (1.0 - SCORING_CONSTANTS.CONFIDENCE_FLOOR);
    return { value: Math.round(multiplier * 1000) / 1000, hasNumericScore: true };
  }
  const map: Record<string, number> = { high: 1.0, medium: 0.85, low: 0.7 };
  return {
    value: map[plan.confidence] ?? 0.85,
    hasNumericScore: false,
  };
}

/**
 * Deadhead penalty: 0-15 points.
 * Computes deadhead % from plan loads.
 */
export function computeDeadheadPenalty(plan: Plan): number {
  let totalDeadhead = 0;
  let totalMiles = 0;
  for (const l of plan.loads) {
    totalDeadhead += l.deadhead_miles;
    totalMiles += (l.load.miles || 0) + l.deadhead_miles;
  }
  if (totalMiles === 0) return 0;
  const deadheadPct = (totalDeadhead / totalMiles) * 100;
  const { DEADHEAD_THRESHOLD_PCT, DEADHEAD_MAX_PENALTY } = SCORING_CONSTANTS;
  if (deadheadPct <= DEADHEAD_THRESHOLD_PCT) return 0;
  const raw = (deadheadPct - DEADHEAD_THRESHOLD_PCT) * 0.5;
  return Math.round(Math.min(DEADHEAD_MAX_PENALTY, Math.max(0, raw)) * 10) / 10;
}

/**
 * Reload bonus: 0-10 points.
 * Requires market temperature data to be available. Falls back to 0 otherwise.
 * NOTE: This function accepts market_temperature as a parameter because
 * the Plan interface does not carry this field — it must be supplied externally.
 */
export function computeReloadBonus(marketTemperature?: string | null): {
  value: number;
  available: boolean;
} {
  if (!marketTemperature) {
    return { value: 0, available: false };
  }
  const { RELOAD_BONUS_HOT, RELOAD_BONUS_NEUTRAL } = SCORING_CONSTANTS;
  if (marketTemperature === 'hot' || marketTemperature === 'warm') {
    return { value: RELOAD_BONUS_HOT, available: true };
  }
  if (marketTemperature === 'neutral') {
    return { value: RELOAD_BONUS_NEUTRAL, available: true };
  }
  return { value: 0, available: true };
}

/**
 * Dwell penalty: 0-10 points.
 * Sums waiting block durations from plan.time_blocks.
 */
export function computeDwellPenalty(plan: Plan): {
  value: number;
  available: boolean;
} {
  const waitBlocks = plan.time_blocks.filter(b => b.block_type === 'waiting');
  if (waitBlocks.length === 0) {
    return { value: 0, available: false };
  }
  const totalWaitMin = waitBlocks.reduce((sum, b) => sum + b.duration_min, 0);
  const { DWELL_THRESHOLD_MIN, DWELL_MAX_PENALTY } = SCORING_CONSTANTS;
  if (totalWaitMin <= DWELL_THRESHOLD_MIN) {
    return { value: 0, available: true };
  }
  const excessHours = (totalWaitMin - DWELL_THRESHOLD_MIN) / 60;
  const raw = excessHours * 3; // 3 points per excess hour
  return {
    value: Math.round(Math.min(DWELL_MAX_PENALTY, raw) * 10) / 10,
    available: true,
  };
}

// ---- Composite Scoring ----

/**
 * Compute full ranking breakdown for a single plan within a batch context.
 * marketTemperature is optional external data (not on the Plan interface).
 */
export function computeRankingBreakdown(
  plan: Plan,
  batchMinCents: number,
  batchMaxCents: number,
  marketTemperature?: string | null,
): RankingBreakdown {
  const cents = plan.profit_per_day_cents ?? parseUsdToCents(plan.profit_per_day_usd);
  const baseProfitScore = computeBaseProfit(cents, batchMinCents, batchMaxCents);
  const conf = computeConfidenceMultiplier(plan);
  const deadheadPenalty = computeDeadheadPenalty(plan);
  const reload = computeReloadBonus(marketTemperature);
  const dwell = computeDwellPenalty(plan);

  const availability: RankingAvailability = {
    has_confidence_score: conf.hasNumericScore,
    reload_bonus_available: reload.available,
    dwell_penalty_available: dwell.available,
  };

  const raw = baseProfitScore * conf.value
    - deadheadPenalty
    + reload.value
    - dwell.value;

  const finalScore = Math.round(Math.max(0, Math.min(100, raw)));

  return {
    profit_per_day_cents: cents,
    base_profit_score: baseProfitScore,
    confidence_multiplier: conf.value,
    deadhead_penalty: deadheadPenalty,
    reload_bonus: reload.value,
    dwell_penalty: dwell.value,
    final_score: finalScore,
    availability,
  };
}

/**
 * Rank a batch of plans in-place. Attaches ranking_breakdown and profit_per_day_cents
 * to each plan, sorts by final_score descending.
 * Returns a NEW array (does not mutate input).
 */
export function rankPlans(
  plans: Plan[],
  marketTemperature?: string | null,
): Plan[] {
  if (plans.length === 0) return [];

  // Compute cents for the batch
  const centsList = plans.map(p =>
    p.profit_per_day_cents ?? parseUsdToCents(p.profit_per_day_usd),
  );
  const batchMinCents = Math.min(...centsList);
  const batchMaxCents = Math.max(...centsList);

  // Score and attach
  const scored = plans.map(plan => {
    const breakdown = computeRankingBreakdown(plan, batchMinCents, batchMaxCents, marketTemperature);
    return {
      ...plan,
      profit_per_day_cents: breakdown.profit_per_day_cents,
      ranking_breakdown: breakdown,
    };
  });

  // Sort by final_score descending (stable)
  scored.sort((a, b) => b.ranking_breakdown.final_score - a.ranking_breakdown.final_score);

  return scored;
}
