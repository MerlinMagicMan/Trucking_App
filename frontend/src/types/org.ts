/**
 * Multi-tenant types (Phase 2A)
 */

export interface Org {
  id: string;
  name: string;
  created_at: string;
}

export interface Truck {
  id: string;
  org_id: string;
  name: string;
  equipment_type: string;
  home_base_city?: string;
  home_base_state?: string;
  created_at: string;
}

export interface RouteRecord {
  id: string;
  org_id: string;
  source: string;
  external_id?: string;
  pickup_city: string;
  pickup_state: string;
  delivery_city: string;
  delivery_state: string;
  rate_total: number;
  miles?: number;
  posted_at?: string;
  created_at: string;
}

export interface PlanHistoryItem {
  id: number;
  timestamp: string;
  snapshot_id: string;
  planning_horizon_days: number;
  plans_generated: number;
  loads_analyzed?: number;
  execution_time_ms?: number;
  warnings?: string[];
}

export interface PlanHistoryDetail extends PlanHistoryItem {
  full_payload: any;
}
