/**
 * API client for backend optimization service
 */
import axios from 'axios';
import type { TruckSnapshot, OptimizeResponse } from '../types/models';
import type { GeneratePlansRequest, GeneratePlansResponse } from '../types/plan';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
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
 *
 * @param request - Truck snapshot + planning parameters
 * @returns 0-3 alternative plans sorted by profit_per_day
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

export default api;
