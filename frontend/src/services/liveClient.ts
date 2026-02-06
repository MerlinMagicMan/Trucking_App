/**
 * Live Client (DEMO-001)
 *
 * Wraps existing api.ts calls to implement DataClient interface.
 * Used when demo mode is disabled and API is configured.
 */

import type { DataClient, CreateTruckInput, CsvRouteRow, RouteFilters, HealthResponse } from './dataClient';
import type { Org, Truck, RouteRecord, PlanHistoryItem, PlanHistoryDetail } from '../types/org';
import type {
  GeneratePlansRequest,
  GeneratePlansResponse,
  CalibrationReport,
} from '../types/plan';
import type { CopilotResponse } from '../types/copilot';
import type {
  IntelResponse,
  LaneIntelData,
  MarketIntelData,
  DestinationIntelData,
} from '../types/intel';
import type { IngestionStatus } from './api';

// Import existing API functions
import {
  fetchOrgs,
  fetchTrucks,
  createTruck as apiCreateTruck,
  fetchRoutes,
  deleteRoute as apiDeleteRoute,
  importRoutes as apiImportRoutes,
  generatePlans as apiGeneratePlans,
  fetchPlanHistory,
  fetchPlanHistoryDetail,
  fetchIngestionStatus,
  checkHealth as apiCheckHealth,
  fetchCalibrationReport,
} from './api';

import { fetchPlanStatus } from './copilot';
import {
  fetchLaneIntel,
  fetchMarketIntel,
  fetchDestinationIntel,
} from './intel';

export const liveClient: DataClient = {
  // Core Data
  async getOrgs(): Promise<Org[]> {
    return fetchOrgs();
  },

  async getTrucks(): Promise<Truck[]> {
    return fetchTrucks();
  },

  async createTruck(data: CreateTruckInput): Promise<Truck> {
    return apiCreateTruck(data);
  },

  async getRoutes(filters?: RouteFilters): Promise<RouteRecord[]> {
    return fetchRoutes(filters);
  },

  async deleteRoute(id: string): Promise<void> {
    return apiDeleteRoute(id);
  },

  async importRoutes(rows: CsvRouteRow[]): Promise<{ imported: number }> {
    return apiImportRoutes(rows);
  },

  // Plans
  async generatePlans(request: GeneratePlansRequest): Promise<GeneratePlansResponse> {
    return apiGeneratePlans(request);
  },

  async getPlanHistory(): Promise<PlanHistoryItem[]> {
    return fetchPlanHistory();
  },

  async getPlanHistoryDetail(id: number): Promise<PlanHistoryDetail> {
    return fetchPlanHistoryDetail(id);
  },

  // Premium Features
  async getPlanStatus(planId: string): Promise<CopilotResponse | null> {
    return fetchPlanStatus(planId);
  },

  async getLaneIntel(origin: string, dest: string): Promise<IntelResponse<LaneIntelData> | null> {
    return fetchLaneIntel(origin, dest);
  },

  async getMarketIntel(geohash: string): Promise<IntelResponse<MarketIntelData> | null> {
    return fetchMarketIntel(geohash);
  },

  async getDestinationIntel(geohash: string): Promise<IntelResponse<DestinationIntelData> | null> {
    return fetchDestinationIntel(geohash);
  },

  async getCalibrationReport(windowDays?: number): Promise<CalibrationReport | null> {
    return fetchCalibrationReport(windowDays);
  },

  // System
  async getIngestionStatus(): Promise<IngestionStatus> {
    return fetchIngestionStatus();
  },

  async checkHealth(): Promise<HealthResponse> {
    return apiCheckHealth();
  },
};
