/**
 * TypeScript types for Plan-based decision system (Phase 0)
 * Matches backend models in app/models/plan.py
 */

export type TimeBlockType =
  | 'drive_empty'
  | 'drive_loaded'
  | 'loading'
  | 'unloading'
  | 'waiting'
  | 'rest_break'
  | 'available';

export type FinancialEventType =
  | 'revenue'
  | 'fuel_cost'
  | 'toll_cost'
  | 'waiting_cost'
  | 'maintenance_reserve'
  | 'opportunity_cost';

export type RiskType =
  | 'hos_tight'
  | 'weather'
  | 'market_weak'
  | 'appointment_tight'
  | 'deadhead_high';

export type RiskSeverity = 'low' | 'medium' | 'high';

export type Confidence = 'low' | 'medium' | 'high';

export interface TimeBlock {
  start_time: string; // ISO datetime
  end_time: string; // ISO datetime
  duration_min: number;
  block_type: TimeBlockType;
  location_lat?: number;
  location_lng?: number;
  location_name?: string;
  related_load_id?: string;
  notes?: string;
}

export interface FinancialEvent {
  timestamp: string; // ISO datetime
  event_type: FinancialEventType;
  amount_usd: number;
  description: string;
  related_load_id?: string;
  calculation_details?: Record<string, any>;
}

export interface RiskSignal {
  timestamp: string; // ISO datetime
  risk_type: RiskType;
  severity: RiskSeverity;
  description: string;
  impact_score: number; // 0-100
}

export interface MaintenanceEvent {
  timestamp: string; // ISO datetime
  odometer_miles: number;
  event_type: 'scheduled' | 'predicted' | 'due';
  description: string;
  estimated_cost_usd?: number;
  estimated_downtime_hours?: number;
}

export interface PickupDeliveryLocation {
  city: string;
  state: string;
  lat: number;
  lng: number;
  window_start?: string; // ISO datetime
  window_end?: string; // ISO datetime
}

export interface CanonicalLoad {
  id: string;
  source: string;
  external_id: string;
  posted_at: string; // ISO datetime
  equipment: string;
  pickup: PickupDeliveryLocation;
  delivery: PickupDeliveryLocation;
  rate_total: number;
  miles?: number;
  notes?: string;
  pickup_geohash?: string;
  delivery_geohash?: string;
}

export interface LoadInPlan {
  load: CanonicalLoad;
  sequence_number: number; // 1, 2, or 3
  deadhead_miles: number;
  revenue_usd: number;
  estimated_fuel_cost_usd: number;
  estimated_toll_cost_usd: number;
  net_revenue_usd: number;
  time_blocks: TimeBlock[];
}

export interface HOSSnapshot {
  drive_remaining_min: number;
  on_duty_remaining_min: number;
  cycle_remaining_min: number;
}

export interface TruckSnapshot {
  snapshot_id?: string;
  timestamp?: string;
  current_lat: number;
  current_lng: number;
  hos: HOSSnapshot;
}

export interface Plan {
  // Identity
  plan_id: string;
  created_at: string; // ISO datetime

  // Context
  truck_snapshot: TruckSnapshot;
  planning_horizon_days: number;

  // Load sequence
  loads: LoadInPlan[];

  // Timeline
  time_blocks: TimeBlock[];
  end_location_lat: number;
  end_location_lng: number;
  end_location_name: string;

  // Financial summary (KEY METRICS)
  total_revenue_usd: number;
  total_costs_usd: number;
  net_profit_usd: number;
  profit_per_day_usd: number; // KEY METRIC
  financial_events: FinancialEvent[];

  // Risk & maintenance
  risk_signals: RiskSignal[];
  maintenance_events: MaintenanceEvent[];

  // Scoring
  plan_score: number; // 0-100
  confidence: Confidence;

  // Explanations
  explanations: string[]; // ≥3 reasons
  warnings: string[];

  // Metadata
  loads_analyzed: number;
  plans_generated: number;
}

export interface GeneratePlansRequest {
  current_lat: number;
  current_lng: number;
  hos: HOSSnapshot;
  planning_horizon_days?: number; // 7-14, default 7
  max_plans?: number; // 1-3, default 3
  radius_miles?: number; // default 250
}

export interface PreflightPreferences {
  current_lat: number;
  current_lng: number;
  planning_horizon_days: 7 | 10 | 14;
  prefer_regions?: string[];
  avoid_regions?: string[];
  home_time_target_days?: number;
  max_deadhead_miles?: number;
  risk_tolerance?: 'low' | 'medium' | 'high';
  hos?: HOSSnapshot;
}

export interface GeneratePlansResponse {
  snapshot_id: string;
  plans: Plan[];
  warnings: string[];
  metadata: {
    planning_horizon_days: number;
    radius_miles: number;
    plans_requested: number;
    plans_generated: number;
  };
}
