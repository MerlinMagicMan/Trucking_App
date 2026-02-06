/**
 * DataClient Interface and Selector (DEMO-001)
 *
 * Facade for all data operations used by the UI.
 * getDataClient() returns demoClient or liveClient based on demo mode.
 */

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
import { isDemoActive } from './demoConfig';

// ---- Input Types ----

export interface CreateTruckInput {
  name: string;
  equipment_type?: string;
  home_base_city?: string;
  home_base_state?: string;
}

export interface CsvRouteRow {
  pickup_city: string;
  pickup_state: string;
  delivery_city: string;
  delivery_state: string;
  miles: string;
  rate_total: string;
  [key: string]: string;
}

export interface RouteFilters {
  pickup_state?: string;
  delivery_state?: string;
  source?: string;
}

export interface HealthResponse {
  status: string;
  message?: string;
}

// ---- DataClient Interface ----

export interface DataClient {
  // Core Data
  getOrgs(): Promise<Org[]>;
  getTrucks(): Promise<Truck[]>;
  createTruck(data: CreateTruckInput): Promise<Truck>;
  getRoutes(filters?: RouteFilters): Promise<RouteRecord[]>;
  deleteRoute(id: string): Promise<void>;
  importRoutes(rows: CsvRouteRow[]): Promise<{ imported: number }>;

  // Plans
  generatePlans(request: GeneratePlansRequest): Promise<GeneratePlansResponse>;
  getPlanHistory(): Promise<PlanHistoryItem[]>;
  getPlanHistoryDetail(id: number): Promise<PlanHistoryDetail>;

  // Premium Features
  getPlanStatus(planId: string): Promise<CopilotResponse | null>;
  getLaneIntel(origin: string, dest: string): Promise<IntelResponse<LaneIntelData> | null>;
  getMarketIntel(geohash: string): Promise<IntelResponse<MarketIntelData> | null>;
  getDestinationIntel(geohash: string): Promise<IntelResponse<DestinationIntelData> | null>;
  getCalibrationReport(windowDays?: number): Promise<CalibrationReport | null>;

  // System
  getIngestionStatus(): Promise<IngestionStatus>;
  checkHealth(): Promise<HealthResponse>;
}

// ---- Client Imports ----
// Import both clients statically - tree shaking will handle unused code
import { demoClient } from './demoClient';
import { liveClient } from './liveClient';

// ---- Client Selector ----

export function getDataClient(): DataClient {
  if (isDemoActive()) {
    return demoClient;
  } else {
    return liveClient;
  }
}

// Re-export for convenience
export { isDemoActive } from './demoConfig';
