/**
 * API client for backend optimization service
 */
import axios from 'axios';
import type { TruckSnapshot, OptimizeResponse } from '../types/models';
import type {
  GeneratePlansRequest, GeneratePlansResponse,
  PredictionSnapshot, PlanOutcome, OutcomeReport, OutcomeSummaryItem,
  DecisionCreate, DecisionResponse, CalibrationReport, RiskOutcomeReport,
} from '../types/plan';
import type { Org, Truck, RouteRecord, PlanHistoryItem, PlanHistoryDetail } from '../types/org';
import { getActiveOrgId } from './orgContext';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Inject X-Org-Id on every request
api.interceptors.request.use((config) => {
  const orgId = getActiveOrgId();
  if (orgId) {
    config.headers['X-Org-Id'] = orgId;
  }
  return config;
});

/**
 * Submit truck snapshot for optimization
 */
export const optimizeRoute = async (
  snapshot: TruckSnapshot,
  radiusMiles: number = 250
): Promise<OptimizeResponse> => {
  const response = await api.post<OptimizeResponse>(
    '/api/optimize',
    snapshot,
    { params: { radius_miles: radiusMiles } }
  );
  return response.data;
};

/**
 * Check API health
 */
export const checkHealth = async (): Promise<{ status: string; message?: string }> => {
  const response = await api.get('/api/health');
  return response.data;
};

/**
 * Check connectors health
 */
export const checkConnectorsHealth = async (): Promise<any> => {
  const response = await api.get('/api/connectors/health');
  return response.data;
};

/**
 * Generate multi-load plans (Phase 0)
 */
export const generatePlans = async (
  request: GeneratePlansRequest
): Promise<GeneratePlansResponse> => {
  const { current_lat, current_lng, hos, planning_horizon_days, max_plans, radius_miles } = request;

  const snapshot: TruckSnapshot = {
    current_lat,
    current_lng,
    hos,
  };

  const params: Record<string, number> = {};
  if (planning_horizon_days !== undefined) params.planning_horizon_days = planning_horizon_days;
  if (max_plans !== undefined) params.max_plans = max_plans;
  if (radius_miles !== undefined) params.radius_miles = radius_miles;

  const response = await api.post<GeneratePlansResponse>(
    '/api/plans/generate',
    snapshot,
    { params }
  );

  return response.data;
};

// ---- Multi-tenant endpoints (Phase 2A) ----

export const fetchOrgs = async (): Promise<Org[]> => {
  const response = await api.get<Org[]>('/api/orgs');
  return response.data;
};

export const fetchTrucks = async (): Promise<Truck[]> => {
  const response = await api.get<Truck[]>('/api/trucks');
  return response.data;
};

export const createTruck = async (body: {
  name: string;
  equipment_type?: string;
  home_base_city?: string;
  home_base_state?: string;
}): Promise<Truck> => {
  const response = await api.post<Truck>('/api/trucks', body);
  return response.data;
};

export const fetchRoutes = async (filters?: {
  pickup_state?: string;
  delivery_state?: string;
  source?: string;
}): Promise<RouteRecord[]> => {
  const response = await api.get<RouteRecord[]>('/api/routes', { params: filters });
  return response.data;
};

export const deleteRoute = async (id: string): Promise<void> => {
  await api.delete(`/api/routes/${id}`);
};

export const importRoutes = async (routes: any[]): Promise<{ imported: number }> => {
  const response = await api.post('/api/routes/import', { routes });
  return response.data;
};

export const fetchPlanHistory = async (): Promise<PlanHistoryItem[]> => {
  const response = await api.get<PlanHistoryItem[]>('/api/plans/history');
  return response.data;
};

export const fetchPlanHistoryDetail = async (id: number): Promise<PlanHistoryDetail> => {
  const response = await api.get<PlanHistoryDetail>(`/api/plans/history/${id}`);
  return response.data;
};

// ---- Ingestion endpoints (Phase 3A) ----

export interface IngestionStatus {
  scheduler: { running: boolean; interval_minutes: number };
  snapshots: { active: number; expired: number; total: number };
}

export const fetchIngestionStatus = async (): Promise<IngestionStatus> => {
  const response = await api.get<IngestionStatus>('/api/ingestion/status');
  return response.data;
};

// ---- Plan Outcomes endpoints (Phase 5, Stratum 4A) ----

export const createPredictionSnapshot = async (planId: string): Promise<PredictionSnapshot> => {
  const response = await api.post<PredictionSnapshot>('/api/outcomes/prediction_snapshot', { plan_id: planId });
  return response.data;
};

export const createOutcome = async (body: {
  plan_id: string;
  prediction_snapshot_id?: string;
}): Promise<PlanOutcome> => {
  const response = await api.post<PlanOutcome>('/api/outcomes', body);
  return response.data;
};

export const updateOutcome = async (
  outcomeId: string,
  body: Partial<{
    actual_revenue: string;
    actual_fuel_spend: string;
    actual_tolls: string;
    actual_maintenance: string;
    actual_other_costs: string;
    actual_miles_loaded: number;
    actual_miles_deadhead: number;
    actual_drive_min: number;
    actual_wait_min: number;
    notes: string;
    status: string;
  }>,
): Promise<PlanOutcome> => {
  const response = await api.patch<PlanOutcome>(`/api/outcomes/${outcomeId}`, body);
  return response.data;
};

export const fetchOutcomeReport = async (planId: string): Promise<OutcomeReport | null> => {
  try {
    const response = await api.get<OutcomeReport>('/api/outcomes/report', { params: { plan_id: planId } });
    return response.data;
  } catch {
    return null;
  }
};

export const fetchOutcomeSummary = async (limit = 20): Promise<OutcomeSummaryItem[]> => {
  try {
    const response = await api.get<OutcomeSummaryItem[]>('/api/outcomes/summary', { params: { limit } });
    return response.data;
  } catch {
    return [];
  }
};

// ---- Decision endpoints (Stratum 4B) ----

export const createDecision = async (body: DecisionCreate): Promise<DecisionResponse> => {
  const response = await api.post<DecisionResponse>('/api/decisions', body);
  return response.data;
};

export const fetchDecisions = async (planId: string): Promise<DecisionResponse[]> => {
  try {
    const response = await api.get<DecisionResponse[]>('/api/decisions', { params: { plan_id: planId } });
    return response.data;
  } catch {
    return [];
  }
};

// ---- Calibration endpoints (Stratum 5A) ----

export const fetchCalibrationReport = async (windowDays?: number): Promise<CalibrationReport | null> => {
  try {
    const params: Record<string, number> = {};
    if (windowDays !== undefined) params.window_days = windowDays;
    const response = await api.get<CalibrationReport>('/api/calibration/report', { params });
    return response.data;
  } catch {
    return null;
  }
};

// ---- Trust endpoints (Stratum 5C) ----

export interface PlanTrustReport {
  confidence_score: number;
  confidence_label: 'high' | 'medium' | 'low' | 'unknown';
  warnings: Array<{
    kind: string;
    severity: 'low' | 'medium' | 'high';
    title: string;
    message: string;
    suggested_action?: string | null;
    details: Record<string, any>;
  }>;
  explanations: string[];
  meta: {
    org_id: string;
    plan_id: string;
    computed_at: string;
    window_days: number;
    offline: boolean;
    sample_size: number;
    profile_confidence: string;
    volatility_pct: Record<string, string>;
    used_calibrated: boolean;
  };
}

export const fetchTrustReport = async (planId: string, windowDays?: number): Promise<PlanTrustReport | null> => {
  try {
    const params: Record<string, any> = { plan_id: planId };
    if (windowDays !== undefined) params.window_days = windowDays;
    const response = await api.get<PlanTrustReport>('/api/trust/report', { params });
    return response.data;
  } catch {
    return null;
  }
};

// ---- Risk Outcome endpoints (Stratum 5D) ----

export const fetchRiskOutcomeReport = async (planId: string): Promise<RiskOutcomeReport | null> => {
  try {
    const response = await api.get<RiskOutcomeReport>('/api/outcomes/risk_report', { params: { plan_id: planId } });
    return response.data;
  } catch {
    return null;
  }
};

export default api;
