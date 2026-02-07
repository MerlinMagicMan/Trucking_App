/**
 * Plan Explanation Generator (NEXT-002 v1.1)
 *
 * Pure, deterministic, rule-based explanation strings.
 * Constraints: ≤90 characters, whole dollar formatting, no randomness.
 */

import type { Plan, RankingBreakdown } from '../types/plan';

/**
 * Format USD as whole dollars: "$420" (never "$420.00" or "$420.50").
 */
function wholeDollars(cents: number): string {
  return `$${Math.round(cents / 100)}`;
}

/**
 * Compute deadhead % from plan loads.
 */
function deadheadPct(plan: Plan): number {
  let totalDead = 0;
  let totalMiles = 0;
  for (const l of plan.loads) {
    totalDead += l.deadhead_miles;
    totalMiles += (l.load.miles || 0) + l.deadhead_miles;
  }
  return totalMiles > 0 ? Math.round((totalDead / totalMiles) * 100) : 0;
}

/**
 * Generate a ≤90-char explanation string for a ranked plan.
 *
 * @param plan - The plan with ranking_breakdown attached
 * @param breakdown - The ranking breakdown (or plan.ranking_breakdown)
 * @param rank - 1-indexed rank within the batch
 * @returns Explanation string, guaranteed ≤90 characters
 */
export function generatePlanExplanation(
  plan: Plan,
  breakdown: RankingBreakdown,
  rank: number,
): string {
  const profitStr = wholeDollars(breakdown.profit_per_day_cents);
  const dh = deadheadPct(plan);

  if (rank === 1) {
    // Top plan
    if (breakdown.deadhead_penalty > 5) {
      return truncate(`Best profit at ${profitStr}/day despite ${dh}% deadhead`);
    }
    if (breakdown.dwell_penalty > 3) {
      return truncate(`Top choice: ${profitStr}/day, watch for wait time`);
    }
    if (breakdown.reload_bonus >= 5 && breakdown.availability.reload_bonus_available) {
      return truncate(`Top choice: ${profitStr}/day with strong reload market`);
    }
    return truncate(`Top choice: ${profitStr}/day with ${dh}% deadhead`);
  }

  if (rank === 2) {
    if (breakdown.deadhead_penalty < 3 && dh < 15) {
      return truncate(`Lower deadhead alternative at ${profitStr}/day`);
    }
    if (breakdown.confidence_multiplier >= 0.95) {
      return truncate(`High confidence option at ${profitStr}/day`);
    }
    return truncate(`Close alternative: ${profitStr}/day, ${dh}% deadhead`);
  }

  // Rank 3+
  if (breakdown.deadhead_penalty === 0) {
    return truncate(`Minimal deadhead option at ${profitStr}/day`);
  }
  if (plan.risk_signals.filter(r => r.severity !== 'low').length === 0) {
    return truncate(`Low-risk alternative at ${profitStr}/day`);
  }
  return truncate(`Alternative: ${profitStr}/day, ${plan.loads.length} loads`);
}

/**
 * Truncate to ≤90 characters.
 */
function truncate(s: string): string {
  if (s.length <= 90) return s;
  return s.slice(0, 87) + '...';
}
