/**
 * TypeScript types matching backend canonical models
 */

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

export interface Recommendation {
  load_id: string;
  rank: 1 | 2 | 3;
  hos_feasible: boolean;
  arrival_at_pickup: string;
  arrival_at_delivery: string;
  reload_score: number;
  confidence: "low" | "medium" | "high";
  explanations: string[];
  deadhead_miles?: number;
  total_miles?: number;
  estimated_total_time_min?: number;
}

export interface TimelineEvent {
  timestamp: string;
  event_type: "current" | "arrive_pickup" | "depart_pickup" | "arrive_delivery" | "available_reload";
  description: string;
  location?: string;
}

export interface ForwardLook {
  horizon_hours: number;
  events: TimelineEvent[];
  reload_market_assessment?: string;
}

export interface OptimizeResponse {
  snapshot_id: string;
  recommendations: Recommendation[];
  forward_look?: ForwardLook;
  warnings: string[];
  loads_analyzed: number;
  loads_feasible: number;
}
