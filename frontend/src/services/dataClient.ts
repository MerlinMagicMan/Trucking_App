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

export interface CreateOutcomeInput {
  plan_id: string;
  prediction_snapshot_id?: string;
}

export interface UpdateOutcomeInput {
  actual_revenue?: string;
  actual_fuel_spend?: string;
  actual_tolls?: string;
  actual_maintenance?: string;
  actual_other_costs?: string;
  actual_miles_loaded?: number;
  actual_miles_deadhead?: number;
  actual_drive_min?: number;
  actual_wait_min?: number;
  notes?: string;
  status?: string;
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
  getNegotiationIntel(origin: string, dest: string, offeredRateUsd: number): Promise<IntelResponse<NegotiationIntelData> | null>;
  getCalibrationReport(windowDays?: number): Promise<CalibrationReport | null>;

  // Outcomes (Stratum 4A)
  getOutcomeReport(planId: string): Promise<OutcomeReport | null>;
  createOutcome(body: CreateOutcomeInput): Promise<PlanOutcome>;
  updateOutcome(outcomeId: string, body: UpdateOutcomeInput): Promise<PlanOutcome>;
  getOutcomeSummary(limit?: number): Promise<OutcomeSummaryItem[]>;
  createPredictionSnapshot(planId: string): Promise<PredictionSnapshot>;

  // Decisions (Stratum 4B)
  createDecision(body: DecisionCreate): Promise<DecisionResponse>;
  getDecisions(planId: string): Promise<DecisionResponse[]>;

  // Trust & Risk (Stratum 5C/5D)
  getTrustReport(planId: string, windowDays?: number): Promise<PlanTrustReport | null>;
  getRiskOutcomeReport(planId: string): Promise<RiskOutcomeReport | null>;

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
