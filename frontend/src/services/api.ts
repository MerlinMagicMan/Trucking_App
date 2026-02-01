/**
 * API client for backend optimization service
 */
import axios from 'axios';
import type { TruckSnapshot, OptimizeResponse } from '../types/models';
import type { GeneratePlansRequest, GeneratePlansResponse } from '../types/plan';
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

export default api;
