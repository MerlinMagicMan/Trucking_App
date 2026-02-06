/**
 * Demo Client (DEMO-001)
 *
 * Implements DataClient using localStorage for persistence.
 * All keys are versioned: demo_v1_{entity}
 */

import type { DataClient, CreateTruckInput, CsvRouteRow, RouteFilters, HealthResponse } from './dataClient';
import type { Org, Truck, RouteRecord, PlanHistoryItem, PlanHistoryDetail } from '../types/org';
import type {
  GeneratePlansRequest,
  GeneratePlansResponse,
  CalibrationReport,
  CalibrationMetric,
} from '../types/plan';
import type { CopilotResponse } from '../types/copilot';
import type {
  IntelResponse,
  LaneIntelData,
  MarketIntelData,
  DestinationIntelData,
} from '../types/intel';
import type { IngestionStatus } from './api';
import { getActiveOrgId } from './orgContext';
import { generateDemoPlans } from './demoPlanGenerator';

// ---- Storage Keys (Versioned) ----

const KEYS = {
  orgs: 'demo_v1_orgs',
  trucks: 'demo_v1_trucks',
  routes: 'demo_v1_routes',
  planHistory: 'demo_v1_plan_history',
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
