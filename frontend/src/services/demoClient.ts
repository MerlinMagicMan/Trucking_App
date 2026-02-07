/**
 * Demo Client (DEMO-001)
 *
 * Implements DataClient using localStorage for persistence.
 * All keys are versioned: demo_v1_{entity}
 */

import type {
  DataClient,
  CreateTruckInput,
  CsvRouteRow,
  RouteFilters,
  HealthResponse,
  CreateOutcomeInput,
  UpdateOutcomeInput,
} from './dataClient';
import type { Org, Truck, RouteRecord, PlanHistoryItem, PlanHistoryDetail } from '../types/org';
import type {
  GeneratePlansRequest,
  GeneratePlansResponse,
  CalibrationReport,
  CalibrationMetric,
  PredictionSnapshot,
  PlanOutcome,
  OutcomeReport,
  OutcomeSummaryItem,
  DecisionCreate,
  DecisionResponse,
  RiskOutcomeReport,
} from '../types/plan';
import type { CopilotResponse } from '../types/copilot';
import type {
  IntelResponse,
  LaneIntelData,
  MarketIntelData,
  DestinationIntelData,
  NegotiationIntelData,
} from '../types/intel';
import type { IngestionStatus, PlanTrustReport } from './api';
import { getActiveOrgId } from './orgContext';
import { generateDemoPlans } from './demoPlanGenerator';
import { rankPlans } from './planRanking';
import { generatePlanExplanation } from './planExplanation';

// ---- Storage Keys (Versioned) ----

const KEYS = {
  orgs: 'demo_v1_orgs',
  trucks: 'demo_v1_trucks',
  routes: 'demo_v1_routes',
  planHistory: 'demo_v1_plan_history',
  outcomes: 'demo_v1_outcomes',
  predictionSnapshots: 'demo_v1_prediction_snapshots',
  decisions: 'demo_v1_decisions',
};

// ---- Storage Helpers ----

function getStorage<T>(key: string): T[] {
  try {
    const data = localStorage.getItem(key);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

function setStorage<T>(key: string, data: T[]): void {
  localStorage.setItem(key, JSON.stringify(data));
}

// ---- Required CSV Columns ----

const REQUIRED_CSV_COLUMNS = [
  'pickup_city',
  'pickup_state',
  'delivery_city',
  'delivery_state',
  'miles',
  'rate_total',
];

// ---- Demo Client Implementation ----

export const demoClient: DataClient = {
  // ---- Core Data ----

  async getOrgs(): Promise<Org[]> {
    return getStorage<Org>(KEYS.orgs);
  },

  async getTrucks(): Promise<Truck[]> {
    const orgId = getActiveOrgId();
    const trucks = getStorage<Truck>(KEYS.trucks);
    return orgId ? trucks.filter((t) => t.org_id === orgId) : trucks;
  },

  async createTruck(data: CreateTruckInput): Promise<Truck> {
    const orgId = getActiveOrgId();
    if (!orgId) {
      throw new Error('No active organization. Please seed an organization first.');
    }

    const truck: Truck = {
      id: crypto.randomUUID(),
      org_id: orgId,
      name: data.name,
      equipment_type: data.equipment_type || 'reefer',
      home_base_city: data.home_base_city,
      home_base_state: data.home_base_state,
      created_at: new Date().toISOString(),
    };

    const trucks = getStorage<Truck>(KEYS.trucks);
    trucks.push(truck);
    setStorage(KEYS.trucks, trucks);

    return truck;
  },

  async getRoutes(filters?: RouteFilters): Promise<RouteRecord[]> {
    const orgId = getActiveOrgId();
    let routes = getStorage<RouteRecord>(KEYS.routes);

    if (orgId) {
      routes = routes.filter((r) => r.org_id === orgId);
    }

    if (filters?.pickup_state) {
      routes = routes.filter((r) =>
        r.pickup_state.toLowerCase() === filters.pickup_state!.toLowerCase()
      );
    }

    if (filters?.delivery_state) {
      routes = routes.filter((r) =>
        r.delivery_state.toLowerCase() === filters.delivery_state!.toLowerCase()
      );
    }

    if (filters?.source) {
      routes = routes.filter((r) => r.source === filters.source);
    }

    return routes;
  },

  async deleteRoute(id: string): Promise<void> {
    const routes = getStorage<RouteRecord>(KEYS.routes);
    const filtered = routes.filter((r) => r.id !== id);
    setStorage(KEYS.routes, filtered);
  },

  async importRoutes(rows: CsvRouteRow[]): Promise<{ imported: number }> {
    // Validate required columns
    if (rows.length > 0) {
      const firstRow = rows[0];
      const missing = REQUIRED_CSV_COLUMNS.filter((col) => !(col in firstRow) || !firstRow[col]);
      if (missing.length > 0) {
        throw new Error(`Missing required columns: ${missing.join(', ')}`);
      }
    }

    const orgId = getActiveOrgId();
    if (!orgId) {
      throw new Error('No active organization. Please seed an organization first.');
    }

    const existingRoutes = getStorage<RouteRecord>(KEYS.routes);
    const newRoutes: RouteRecord[] = rows.map((row) => ({
      id: crypto.randomUUID(),
      org_id: orgId,
      source: 'csv-import',
      external_id: undefined,
      pickup_city: row.pickup_city,
      pickup_state: row.pickup_state.toUpperCase(),
      delivery_city: row.delivery_city,
      delivery_state: row.delivery_state.toUpperCase(),
      rate_total: parseFloat(row.rate_total) || 0,
      miles: parseInt(row.miles, 10) || undefined,
      posted_at: undefined,
      created_at: new Date().toISOString(),
    }));

    setStorage(KEYS.routes, [...existingRoutes, ...newRoutes]);
    return { imported: newRoutes.length };
  },

  // ---- Plans ----

  async generatePlans(request: GeneratePlansRequest): Promise<GeneratePlansResponse> {
    const routes = await this.getRoutes();
    const response = generateDemoPlans(request, routes);

    // NEXT-002: Apply ranking + explanations
    if (response.plans.length > 0) {
      const ranked = rankPlans(response.plans);
      ranked.forEach((plan, i) => {
        if (plan.ranking_breakdown) {
          plan.ranking_explanation = generatePlanExplanation(plan, plan.ranking_breakdown, i + 1);
        }
      });
      response.plans = ranked;
    }

    // Save to plan history
    if (response.plans.length > 0) {
      const history = getStorage<PlanHistoryItem>(KEYS.planHistory);
      const historyEntry: PlanHistoryItem = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        snapshot_id: response.snapshot_id,
        planning_horizon_days: response.metadata.planning_horizon_days,
        plans_generated: response.metadata.plans_generated,
        loads_analyzed: routes.length,
        execution_time_ms: Math.round(Math.random() * 500 + 100),
        warnings: response.warnings,
      };
      history.unshift(historyEntry);
      setStorage(KEYS.planHistory, history.slice(0, 50)); // Keep last 50

      // Store full payload for detail view
      localStorage.setItem(
        `demo_v1_plan_detail_${historyEntry.id}`,
        JSON.stringify(response)
      );
    }

    return response;
  },

  async getPlanHistory(): Promise<PlanHistoryItem[]> {
    return getStorage<PlanHistoryItem>(KEYS.planHistory);
  },

  async getPlanHistoryDetail(id: number): Promise<PlanHistoryDetail> {
    const history = getStorage<PlanHistoryItem>(KEYS.planHistory);
    const item = history.find((h) => h.id === id);

    if (!item) {
      throw new Error(`Plan history entry ${id} not found`);
    }

    // Try to get stored full payload
    const storedPayload = localStorage.getItem(`demo_v1_plan_detail_${id}`);
    const fullPayload = storedPayload ? JSON.parse(storedPayload) : null;

    return {
      ...item,
      full_payload: fullPayload,
    };
  },

  // ---- Premium Features (Mock Data) ----

  async getPlanStatus(planId: string): Promise<CopilotResponse | null> {
    const now = new Date().toISOString();
    return {
      meta: {
        org_id: getActiveOrgId() || 'demo-org',
        plan_id: planId,
        as_of: now,
        evaluated_at: now,
        windows: { lane: '6h', market: '6h', destination: '6h' },
        data_sources: { lane: 'demo', market: 'demo', destination: 'demo' },
        offline: false,
        trust: null,
      },
      status: 'ok',
      signals: [],
      suggestions: [],
      explanations: ['Demo mode: No degradation signals detected.'],
    };
  },

  async getLaneIntel(_origin: string, _dest: string): Promise<IntelResponse<LaneIntelData> | null> {
    const now = new Date().toISOString();
    return {
      meta: {
        org_id: getActiveOrgId() || 'demo-org',
        window: '6h',
        window_start: now,
        window_end: now,
        source: 'demo',
        computed_at: now,
        data_freshness_seconds: 0,
        sample_size: 42,
      },
      data: {
        load_count: 42,
        rate_p25: 1850,
        rate_p50: 2100,
        rate_p75: 2400,
        rate_p90: 2800,
        avg_rate_per_mile: 2.15,
        avg_miles: 450,
        time_to_cover_p50_minutes: 180,
        volatility_score: 0.35,
      },
      explanations: ['Demo mode: Sample lane intelligence data.'],
    };
  },

  async getMarketIntel(_geohash: string): Promise<IntelResponse<MarketIntelData> | null> {
    const now = new Date().toISOString();
    return {
      meta: {
        org_id: getActiveOrgId() || 'demo-org',
        window: '6h',
        window_start: now,
        window_end: now,
        source: 'demo',
        computed_at: now,
        data_freshness_seconds: 0,
        sample_size: 128,
      },
      data: {
        active_load_count_avg: 128,
        new_loads_count: 45,
        expired_loads_count: 12,
        reload_depth: 2.3,
        market_temperature: 'warm',
      },
      explanations: ['Demo mode: Sample market intelligence data.'],
    };
  },

  async getDestinationIntel(_geohash: string): Promise<IntelResponse<DestinationIntelData> | null> {
    const now = new Date().toISOString();
    return {
      meta: {
        org_id: getActiveOrgId() || 'demo-org',
        window: '6h',
        window_start: now,
        window_end: now,
        source: 'demo',
        computed_at: now,
        data_freshness_seconds: 0,
        sample_size: 85,
      },
      data: {
        reload_probability: 0.78,
        avg_time_to_first_reload_minutes: 240,
        efficiency_score: 0.82,
        volatility_score: 0.28,
      },
      explanations: ['Demo mode: Sample destination intelligence data.'],
    };
  },

  async getNegotiationIntel(
    _origin: string,
    _dest: string,
    offeredRateUsd: number,
  ): Promise<IntelResponse<NegotiationIntelData> | null> {
    const now = new Date().toISOString();
    // Deterministic negotiation intel based on offered rate
    const anchorRate = offeredRateUsd * 1.15;
    const suggestedCounter = offeredRateUsd * 1.08;
    const fastAccept = offeredRateUsd * 1.02;
    const walkAway = offeredRateUsd * 0.85;

    return {
      meta: {
        org_id: getActiveOrgId() || 'demo-org',
        window: '6h',
        window_start: now,
        window_end: now,
        source: 'demo',
        computed_at: now,
        data_freshness_seconds: 0,
        sample_size: 32,
      },
      data: {
        position: offeredRateUsd > 2000 ? 'weak' : 'strong',
        anchor_usd: Math.round(anchorRate),
        suggested_counter_usd: Math.round(suggestedCounter),
        fast_accept_usd: Math.round(fastAccept),
        walk_away_usd: Math.round(walkAway),
      },
      explanations: ['Demo mode: Sample negotiation intelligence data.'],
    };
  },

  async getCalibrationReport(windowDays?: number): Promise<CalibrationReport | null> {
    const now = new Date().toISOString();
    const metrics: CalibrationMetric[] = [
      {
        name: 'revenue',
        predicted_avg: '2450.00',
        actual_avg: '2380.00',
        mean_error: '-70.00',
        mae: '85.00',
        mean_variance_pct: '2.9',
        direction: 'over',
        sample_size: 15,
        worst_case_pct: '8.5',
      },
      {
        name: 'fuel_cost',
        predicted_avg: '580.00',
        actual_avg: '595.00',
        mean_error: '15.00',
        mae: '22.00',
        mean_variance_pct: '2.5',
        direction: 'under',
        sample_size: 15,
        worst_case_pct: '6.2',
      },
      {
        name: 'net_profit',
        predicted_avg: '1200.00',
        actual_avg: '1150.00',
        mean_error: '-50.00',
        mae: '65.00',
        mean_variance_pct: '4.2',
        direction: 'over',
        sample_size: 15,
        worst_case_pct: '9.8',
      },
    ];

    return {
      org_id: getActiveOrgId() || 'demo-org',
      window_days: windowDays || 14,
      computed_at: now,
      sample_size: 15,
      accuracy_score: '75.5',
      metrics,
      insights: [
        'Demo mode: Revenue predictions are slightly optimistic.',
        'Fuel costs tracking within acceptable range.',
        'Consider adjusting profit margin calculations.',
      ],
    };
  },

  // ---- Outcomes (Stratum 4A) ----

  async getOutcomeReport(planId: string): Promise<OutcomeReport | null> {
    const outcomes = getStorage<PlanOutcome>(KEYS.outcomes);
    const outcome = outcomes.find((o) => o.plan_id === planId);
    const snapshots = getStorage<PredictionSnapshot>(KEYS.predictionSnapshots);
    const snapshot = snapshots.find((s) => s.plan_id === planId);

    if (!outcome && !snapshot) {
      return null;
    }

    // Calculate deltas if we have both predicted and actual
    const deltas: OutcomeReport['deltas'] = [];
    if (snapshot && outcome) {
      const addDelta = (field: string, predicted: string | null | undefined, actual: string | null | undefined) => {
        if (predicted != null && actual != null) {
          const predNum = parseFloat(predicted);
          const actNum = parseFloat(actual);
          const delta = actNum - predNum;
          const variancePct = predNum !== 0 ? ((delta / predNum) * 100).toFixed(1) : '0.0';
          deltas.push({
            field,
            predicted,
            actual,
            delta: delta.toFixed(2),
            variance_pct: variancePct,
          });
        }
      };
      addDelta('revenue', snapshot.predicted_revenue, outcome.actual_revenue);
      addDelta('costs', snapshot.predicted_costs, outcome.actual_fuel_spend);
      if (snapshot.predicted_net_profit && outcome.actual_revenue && outcome.actual_fuel_spend) {
        const actualProfit = parseFloat(outcome.actual_revenue) - parseFloat(outcome.actual_fuel_spend);
        addDelta('net_profit', snapshot.predicted_net_profit, actualProfit.toFixed(2));
      }
    }

    return {
      plan_id: planId,
      prediction_snapshot_id: snapshot?.id || null,
      outcome_id: outcome?.id || null,
      outcome_status: outcome?.status || null,
      predicted_summary: {
        revenue: snapshot?.predicted_revenue || '2450.00',
        costs: snapshot?.predicted_costs || '850.00',
        net_profit: snapshot?.predicted_net_profit || '1600.00',
      },
      actual_summary: outcome
        ? {
            revenue: outcome.actual_revenue,
            costs: outcome.actual_fuel_spend,
            net_profit:
              outcome.actual_revenue && outcome.actual_fuel_spend
                ? (
                    parseFloat(outcome.actual_revenue) -
                    parseFloat(outcome.actual_fuel_spend || '0')
                  ).toFixed(2)
                : null,
          }
        : {},
      actuals: outcome
        ? {
            revenue: outcome.actual_revenue,
            fuel_spend: outcome.actual_fuel_spend,
            tolls: outcome.actual_tolls,
            maintenance: outcome.actual_maintenance,
            other_costs: outcome.actual_other_costs,
            miles_loaded: outcome.actual_miles_loaded,
            miles_deadhead: outcome.actual_miles_deadhead,
            drive_min: outcome.actual_drive_min,
            wait_min: outcome.actual_wait_min,
            notes: outcome.notes,
          }
        : undefined,
      deltas,
      flags: outcome?.status === 'complete'
        ? [{ flag: 'complete', severity: 'low', summary: 'Outcome fully recorded' }]
        : [],
      explanations: outcome?.status === 'complete'
        ? ['Outcome complete. Learning loop data available.']
        : ['Demo mode: Enter actuals to complete this outcome.'],
    };
  },

  async createOutcome(body: CreateOutcomeInput): Promise<PlanOutcome> {
    const orgId = getActiveOrgId();
    if (!orgId) {
      throw new Error('No active organization');
    }

    const outcome: PlanOutcome = {
      id: crypto.randomUUID(),
      org_id: orgId,
      plan_id: body.plan_id,
      prediction_snapshot_id: body.prediction_snapshot_id || null,
      status: 'pending',
      source: 'demo',
      actual_revenue: null,
      actual_fuel_spend: null,
      actual_tolls: null,
      actual_maintenance: null,
      actual_other_costs: null,
      actual_miles_loaded: null,
      actual_miles_deadhead: null,
      actual_drive_min: null,
      actual_wait_min: null,
      actual: {},
      notes: null,
      recorded_at: new Date().toISOString(),
      completed_at: null,
    };

    const outcomes = getStorage<PlanOutcome>(KEYS.outcomes);
    outcomes.push(outcome);
    setStorage(KEYS.outcomes, outcomes);

    return outcome;
  },

  async updateOutcome(outcomeId: string, body: UpdateOutcomeInput): Promise<PlanOutcome> {
    const outcomes = getStorage<PlanOutcome>(KEYS.outcomes);
    const index = outcomes.findIndex((o) => o.id === outcomeId);

    if (index === -1) {
      throw new Error(`Outcome ${outcomeId} not found`);
    }

    const updated: PlanOutcome = {
      ...outcomes[index],
      ...body,
      status: body.status as 'pending' | 'partial' | 'complete' || outcomes[index].status,
      completed_at: body.status === 'complete' ? new Date().toISOString() : outcomes[index].completed_at,
    };

    outcomes[index] = updated;
    setStorage(KEYS.outcomes, outcomes);

    return updated;
  },

  async getOutcomeSummary(limit = 20): Promise<OutcomeSummaryItem[]> {
    const outcomes = getStorage<PlanOutcome>(KEYS.outcomes);
    const snapshots = getStorage<PredictionSnapshot>(KEYS.predictionSnapshots);

    return outcomes.slice(0, limit).map((outcome) => {
      const snapshot = snapshots.find((s) => s.plan_id === outcome.plan_id);
      const predictedProfit = snapshot?.predicted_net_profit;
      const actualRevenue = outcome.actual_revenue ? parseFloat(outcome.actual_revenue) : null;
      const actualCosts = outcome.actual_fuel_spend ? parseFloat(outcome.actual_fuel_spend) : 0;
      const actualProfit = actualRevenue !== null ? (actualRevenue - actualCosts).toFixed(2) : null;

      let variancePct: string | null = null;
      if (predictedProfit && actualProfit) {
        const predicted = parseFloat(predictedProfit);
        const actual = parseFloat(actualProfit);
        if (predicted !== 0) {
          variancePct = (((actual - predicted) / Math.abs(predicted)) * 100).toFixed(1);
        }
      }

      return {
        plan_id: outcome.plan_id,
        outcome_id: outcome.id,
        status: outcome.status,
        predicted_net_profit: predictedProfit || null,
        actual_net_profit: actualProfit,
        profit_variance_pct: variancePct,
        predicted_duration_min: snapshot?.predicted_duration_min || null,
        actual_duration_min:
          outcome.actual_drive_min != null && outcome.actual_wait_min != null
            ? outcome.actual_drive_min + outcome.actual_wait_min
            : null,
        time_variance_pct: null,
        recorded_at: outcome.recorded_at,
        completed_at: outcome.completed_at || null,
      };
    });
  },

  async createPredictionSnapshot(planId: string): Promise<PredictionSnapshot> {
    const orgId = getActiveOrgId();
    if (!orgId) {
      throw new Error('No active organization');
    }

    // Try to find the plan in history to get predictions
    const history = getStorage<PlanHistoryItem>(KEYS.planHistory);
    const historyItem = history.find((h) => {
      const detail = localStorage.getItem(`demo_v1_plan_detail_${h.id}`);
      if (detail) {
        const parsed = JSON.parse(detail);
        return parsed.plans?.some((p: { plan_id: string }) => p.plan_id === planId);
      }
      return false;
    });

    let predictedValues = {
      revenue: '2450.00',
      costs: '850.00',
      net_profit: '1600.00',
      profit_per_day: '228.57',
      miles_total: 850,
      miles_deadhead: 120,
      duration_min: 600,
      num_loads: 2,
    };

    if (historyItem) {
      const detail = localStorage.getItem(`demo_v1_plan_detail_${historyItem.id}`);
      if (detail) {
        const parsed = JSON.parse(detail);
        const plan = parsed.plans?.find((p: { plan_id: string }) => p.plan_id === planId);
        if (plan) {
          predictedValues = {
            revenue: plan.total_revenue_usd?.toFixed(2) || predictedValues.revenue,
            costs: plan.total_costs_usd?.toFixed(2) || predictedValues.costs,
            net_profit: plan.net_profit_usd?.toFixed(2) || predictedValues.net_profit,
            profit_per_day: plan.profit_per_day_usd?.toFixed(2) || predictedValues.profit_per_day,
            miles_total: plan.loads?.reduce((sum: number, l: { deadhead_miles?: number }) => sum + (l.deadhead_miles || 0), 0) || predictedValues.miles_total,
            miles_deadhead: plan.loads?.[0]?.deadhead_miles || predictedValues.miles_deadhead,
            duration_min: plan.time_blocks?.reduce((sum: number, b: { duration_min?: number }) => sum + (b.duration_min || 0), 0) || predictedValues.duration_min,
            num_loads: plan.loads?.length || predictedValues.num_loads,
          };
        }
      }
    }

    const snapshot: PredictionSnapshot = {
      id: crypto.randomUUID(),
      org_id: orgId,
      plan_id: planId,
      plan_generation_event_id: null,
      created_at: new Date().toISOString(),
      predicted_revenue: predictedValues.revenue,
      predicted_costs: predictedValues.costs,
      predicted_net_profit: predictedValues.net_profit,
      predicted_profit_per_day: predictedValues.profit_per_day,
      predicted_miles_total: predictedValues.miles_total,
      predicted_miles_deadhead: predictedValues.miles_deadhead,
      predicted_duration_min: predictedValues.duration_min,
      predicted_num_loads: predictedValues.num_loads,
      predicted: predictedValues,
    };

    const snapshots = getStorage<PredictionSnapshot>(KEYS.predictionSnapshots);
    snapshots.push(snapshot);
    setStorage(KEYS.predictionSnapshots, snapshots);

    return snapshot;
  },

  // ---- Decisions (Stratum 4B) ----

  async createDecision(body: DecisionCreate): Promise<DecisionResponse> {
    const orgId = getActiveOrgId();
    if (!orgId) {
      throw new Error('No active organization');
    }

    let outcomeId: string | null = null;
    let predictionSnapshotId: string | null = null;

    // On accept, create snapshot + outcome if not exists
    if (body.decision_type === 'accepted') {
      const snapshots = getStorage<PredictionSnapshot>(KEYS.predictionSnapshots);
      let snapshot = snapshots.find((s) => s.plan_id === body.plan_id);
      if (!snapshot) {
        snapshot = await this.createPredictionSnapshot(body.plan_id);
      }
      predictionSnapshotId = snapshot.id;

      const outcomes = getStorage<PlanOutcome>(KEYS.outcomes);
      let outcome = outcomes.find((o) => o.plan_id === body.plan_id);
      if (!outcome) {
        outcome = await this.createOutcome({
          plan_id: body.plan_id,
          prediction_snapshot_id: snapshot.id,
        });
      }
      outcomeId = outcome.id;
    }

    const decision: DecisionResponse = {
      id: Date.now(),
      org_id: orgId,
      plan_id: body.plan_id,
      decision_type: body.decision_type,
      reason: body.reason || null,
      outcome_id: outcomeId,
      prediction_snapshot_id: predictionSnapshotId,
      decision_context_snapshot_id: null,
      timestamp: new Date().toISOString(),
    };

    const decisions = getStorage<DecisionResponse>(KEYS.decisions);
    decisions.unshift(decision);
    setStorage(KEYS.decisions, decisions);

    return decision;
  },

  async getDecisions(planId: string): Promise<DecisionResponse[]> {
    const decisions = getStorage<DecisionResponse>(KEYS.decisions);
    return decisions.filter((d) => d.plan_id === planId);
  },

  // ---- Trust & Risk (Stratum 5C/5D) ----

  async getTrustReport(planId: string, windowDays?: number): Promise<PlanTrustReport | null> {
    const now = new Date().toISOString();
    return {
      confidence_score: 78,
      confidence_label: 'medium',
      warnings: [
        {
          kind: 'volatility_high',
          severity: 'low',
          title: 'Lane Rate Volatility',
          message: 'Historical rate variance is 18% on this lane.',
          suggested_action: 'Consider locking in rate early.',
          details: { volatility_pct: '18.0' },
        },
      ],
      explanations: ['Demo mode: Sample trust assessment.'],
      meta: {
        org_id: getActiveOrgId() || 'demo-org',
        plan_id: planId,
        computed_at: now,
        window_days: windowDays || 14,
        offline: false,
        sample_size: 15,
        profile_confidence: '0.85',
        volatility_pct: { revenue: '5.2', costs: '8.1' },
        used_calibrated: true,
      },
    };
  },

  async getRiskOutcomeReport(planId: string): Promise<RiskOutcomeReport | null> {
    const now = new Date().toISOString();
    const outcomes = getStorage<PlanOutcome>(KEYS.outcomes);
    const outcome = outcomes.find((o) => o.plan_id === planId);
    const decisions = getStorage<DecisionResponse>(KEYS.decisions);
    const decision = decisions.find((d) => d.plan_id === planId && d.decision_type === 'accepted');

    return {
      org_id: getActiveOrgId() || 'demo-org',
      plan_id: planId,
      computed_at: now,
      decision_context: decision
        ? {
            captured_at: decision.timestamp,
            trust_score: 78,
            trust_label: 'medium',
            trust_warning_count: 1,
            copilot_status: 'ok',
            copilot_signal_count: 0,
            copilot_high_severity_count: 0,
            calibration_sample_size: 15,
            calibration_applied: 'true',
            plan_revenue: '2450.00',
            plan_costs: '850.00',
            plan_net_profit: '1600.00',
          }
        : null,
      pre_decision_warnings: [],
      outcome_summary: outcome
        ? {
            status: outcome.status,
            completed_at: outcome.completed_at || null,
            actual_revenue: outcome.actual_revenue || null,
            actual_costs: outcome.actual_fuel_spend || null,
            actual_net_profit:
              outcome.actual_revenue && outcome.actual_fuel_spend
                ? (parseFloat(outcome.actual_revenue) - parseFloat(outcome.actual_fuel_spend)).toFixed(2)
                : null,
            revenue_variance_pct: null,
            costs_variance_pct: null,
            profit_variance_pct: null,
            major_variance_fields: [],
          }
        : null,
      warning_correlations: [],
      accuracy_assessment: 'insufficient_data',
      accuracy_score: 0,
      explanations: ['Demo mode: Risk outcome tracking is simulated.'],
      has_decision_context: !!decision,
      has_completed_outcome: outcome?.status === 'complete',
    };
  },

  // ---- System ----

  async getIngestionStatus(): Promise<IngestionStatus> {
    return {
      scheduler: { running: true, interval_minutes: 15 },
      snapshots: { active: 5, expired: 0, total: 5 },
    };
  },

  async checkHealth(): Promise<HealthResponse> {
    return {
      status: 'demo',
      message: 'Demo mode active — data stored in localStorage',
    };
  },
};
