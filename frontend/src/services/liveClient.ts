/**
 * Live Client (DEMO-001)
 *
 * Wraps existing api.ts calls to implement DataClient interface.
 * Used when demo mode is disabled and API is configured.
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
  fetchOutcomeReport,
  createOutcome as apiCreateOutcome,
  updateOutcome as apiUpdateOutcome,
  fetchOutcomeSummary,
  createPredictionSnapshot as apiCreatePredictionSnapshot,
  createDecision as apiCreateDecision,
  fetchDecisions,
  fetchTrustReport,
  fetchRiskOutcomeReport,
} from './api';

import { fetchPlanStatus } from './copilot';
import {
  fetchLaneIntel,
  fetchMarketIntel,
  fetchDestinationIntel,
  fetchNegotiationIntel,
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

  async getNegotiationIntel(
    origin: string,
    dest: string,
    offeredRateUsd: number,
  ): Promise<IntelResponse<NegotiationIntelData> | null> {
    return fetchNegotiationIntel(origin, dest, offeredRateUsd);
  },

  async getCalibrationReport(windowDays?: number): Promise<CalibrationReport | null> {
    return fetchCalibrationReport(windowDays);
  },

  // Outcomes (Stratum 4A)
  async getOutcomeReport(planId: string): Promise<OutcomeReport | null> {
    return fetchOutcomeReport(planId);
  },

  async createOutcome(body: CreateOutcomeInput): Promise<PlanOutcome> {
    return apiCreateOutcome(body);
  },

  async updateOutcome(outcomeId: string, body: UpdateOutcomeInput): Promise<PlanOutcome> {
    return apiUpdateOutcome(outcomeId, body);
  },

  async getOutcomeSummary(limit?: number): Promise<OutcomeSummaryItem[]> {
    return fetchOutcomeSummary(limit);
  },

  async createPredictionSnapshot(planId: string): Promise<PredictionSnapshot> {
    return apiCreatePredictionSnapshot(planId);
  },

  // Decisions (Stratum 4B)
  async createDecision(body: DecisionCreate): Promise<DecisionResponse> {
    return apiCreateDecision(body);
  },

  async getDecisions(planId: string): Promise<DecisionResponse[]> {
    return fetchDecisions(planId);
  },

  // Trust & Risk (Stratum 5C/5D)
  async getTrustReport(planId: string, windowDays?: number): Promise<PlanTrustReport | null> {
    return fetchTrustReport(planId, windowDays);
  },

  async getRiskOutcomeReport(planId: string): Promise<RiskOutcomeReport | null> {
    return fetchRiskOutcomeReport(planId);
  },

  // System
  async getIngestionStatus(): Promise<IngestionStatus> {
    return fetchIngestionStatus();
  },

  async checkHealth(): Promise<HealthResponse> {
    return apiCheckHealth();
  },
};
