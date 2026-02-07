/**
 * Snapshot Storage (Wave 2: Snapshot Flow)
 *
 * Persists snapshot data to localStorage for offline/demo mode compatibility.
 * Replaces sessionStorage usage for hard-refresh resilience.
 */

const STORAGE_KEY = 'demo_v1_active_snapshot';

export interface SnapshotRecommendation {
  id: string;
  category: 'operational' | 'negotiation' | 'risk';
  title: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
  action?: string;
}

export interface SnapshotProjection {
  scenario: 'best' | 'base' | 'worst';
  profit_per_day: number;
  probability: number;
  description: string;
}

export interface ActiveSnapshot {
  id: string;
  created_at: string;
  plan_id: string;
  plan_summary: {
    total_revenue: number;
    total_costs: number;
    net_profit: number;
    profit_per_day: number;
    num_loads: number;
    end_location: string;
    confidence: string;
  };
  trust_score?: number | null;
  trust_label?: string | null;
  trust_warnings?: number;
  recommendations: SnapshotRecommendation[];
  projections: SnapshotProjection[];
  lane_repeat_insights: string[];
}

/**
 * Save a snapshot to localStorage
 */
export function saveActiveSnapshot(snapshot: ActiveSnapshot): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
}

/**
 * Load the active snapshot from localStorage
 */
export function getActiveSnapshot(): ActiveSnapshot | null {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

/**
 * Clear the active snapshot
 */
export function clearActiveSnapshot(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * Check if an active snapshot exists
 */
export function hasActiveSnapshot(): boolean {
  return localStorage.getItem(STORAGE_KEY) !== null;
}

/**
 * Generate deterministic recommendations from plan data
 */
export function generateRecommendations(
  planSummary: ActiveSnapshot['plan_summary'],
  trustScore?: number | null,
): SnapshotRecommendation[] {
  const recs: SnapshotRecommendation[] = [];

  // Operational recommendations
  if (planSummary.profit_per_day < 300) {
    recs.push({
      id: 'op-1',
      category: 'operational',
      title: 'Consider Multi-Load Strategy',
      description: 'Current profit/day is below target. Adding a second load could increase daily earnings by 20-40%.',
      impact: 'high',
      action: 'Search for loads near delivery point',
    });
  }

  if (planSummary.num_loads === 1) {
    recs.push({
      id: 'op-2',
      category: 'operational',
      title: 'Maximize HOS Utilization',
      description: 'Single-load plans often leave HOS capacity unused. Consider chaining loads.',
      impact: 'medium',
      action: 'Check reload opportunities',
    });
  }

  recs.push({
    id: 'op-3',
    category: 'operational',
    title: 'Fuel Stop Optimization',
    description: 'Plan fuel stops at lower-cost locations along your route to save $50-100 per trip.',
    impact: 'low',
    action: 'Review fuel prices on route',
  });

  // Negotiation recommendations
  const ratePerMile = planSummary.total_revenue / (planSummary.num_loads * 400); // estimate
  if (ratePerMile < 2.5) {
    recs.push({
      id: 'neg-1',
      category: 'negotiation',
      title: 'Rate Below Market Average',
      description: `Current rate is below the $2.50/mile market average. Consider counter-offering.`,
      impact: 'high',
      action: 'Request rate increase',
    });
  } else {
    recs.push({
      id: 'neg-2',
      category: 'negotiation',
      title: 'Favorable Rate Secured',
      description: 'Your negotiated rate is at or above market. Accept quickly to lock it in.',
      impact: 'medium',
      action: 'Confirm acceptance',
    });
  }

  recs.push({
    id: 'neg-3',
    category: 'negotiation',
    title: 'Detention Time Clause',
    description: 'Ensure detention time is included in rate negotiations. Average wait times can add 2+ hours.',
    impact: 'medium',
  });

  // Risk recommendations
  if (trustScore !== null && trustScore !== undefined && trustScore < 60) {
    recs.push({
      id: 'risk-1',
      category: 'risk',
      title: 'Low Confidence Score',
      description: `Trust score of ${trustScore} indicates higher prediction uncertainty. Build in buffer time.`,
      impact: 'high',
      action: 'Add 15% time buffer',
    });
  }

  if (planSummary.confidence === 'low') {
    recs.push({
      id: 'risk-2',
      category: 'risk',
      title: 'Volatility Warning',
      description: 'Lane conditions are variable. Monitor market changes and have backup plans ready.',
      impact: 'medium',
      action: 'Set rate alerts',
    });
  }

  recs.push({
    id: 'risk-3',
    category: 'risk',
    title: 'Weather & Traffic Check',
    description: 'Always verify weather and traffic conditions before departure for on-time delivery.',
    impact: 'low',
    action: 'Check conditions',
  });

  return recs;
}

/**
 * Generate deterministic forward-look projections
 */
export function generateProjections(
  planSummary: ActiveSnapshot['plan_summary'],
): SnapshotProjection[] {
  const baseProfitPerDay = planSummary.profit_per_day;

  return [
    {
      scenario: 'best',
      profit_per_day: Math.round(baseProfitPerDay * 1.25),
      probability: 20,
      description: 'Quick unload, immediate reload, favorable rates. Potential for +25% daily earnings.',
    },
    {
      scenario: 'base',
      profit_per_day: Math.round(baseProfitPerDay),
      probability: 60,
      description: 'Standard execution with expected wait times and market rates.',
    },
    {
      scenario: 'worst',
      profit_per_day: Math.round(baseProfitPerDay * 0.7),
      probability: 20,
      description: 'Extended detention, rate drops, or mechanical issues. Plan for -30% in worst case.',
    },
  ];
}

/**
 * Generate lane repeat insights
 */
export function generateLaneInsights(
  planSummary: ActiveSnapshot['plan_summary'],
): string[] {
  return [
    `If you repeat this ${planSummary.end_location} lane, historical data suggests 70% reload probability within 4 hours.`,
    `Average drivers running this route 3x/week earn $${Math.round(planSummary.profit_per_day * 3 * 4)}/month.`,
    `Rate trends show this lane is ${planSummary.profit_per_day > 350 ? 'above' : 'at or below'} seasonal average.`,
    `Consider establishing relationships with shippers in ${planSummary.end_location} for preferential rates.`,
  ];
}
