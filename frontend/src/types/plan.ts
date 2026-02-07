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
  confidence_score?: number | null; // Numeric confidence score (0-100) for premium tier weighting

  // Explanations
  explanations: string[]; // ≥3 reasons
  warnings: string[];

  // Metadata
  loads_analyzed: number;
  plans_generated: number;

  // Calibration (Stratum 5B)
  estimates_raw?: PlanEstimates;
  estimates_calibrated?: PlanEstimates | null;
  calibration_meta?: CalibrationAppliedMeta;

  // NEXT-002: Ranking (optional, attached by ranking engine)
  profit_per_day_cents?: number;
  ranking_explanation?: string;
  ranking_breakdown?: RankingBreakdown;
}

// NEXT-002: Ranking breakdown (v1.1 — integer cents, batch-normalized)

export interface RankingAvailability {
  has_confidence_score: boolean;
  reload_bonus_available: boolean;
  dwell_penalty_available: boolean;
}

export interface RankingBreakdown {
  profit_per_day_cents: number;
  base_profit_score: number;       // 0-100, within-batch normalized
  confidence_multiplier: number;   // 0.7-1.0
  deadhead_penalty: number;        // 0-15
  reload_bonus: number;            // 0-10 (0 when data unavailable)
  dwell_penalty: number;           // 0-10 (0 when no wait blocks)
  final_score: number;             // 0-100
  availability: RankingAvailability;
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

// Phase 5: Plan Outcomes (Stratum 4A) — money as string (Decimal)

export interface PredictionSnapshot {
  id: string;
  org_id: string;
  plan_id: string;
  plan_generation_event_id?: number | null;
  created_at: string;
  predicted_revenue?: string | null;
  predicted_costs?: string | null;
  predicted_net_profit?: string | null;
  predicted_profit_per_day?: string | null;
  predicted_miles_total?: number | null;
  predicted_miles_deadhead?: number | null;
  predicted_duration_min?: number | null;
  predicted_num_loads?: number | null;
  predicted: Record<string, any>;
}

export interface PlanOutcome {
  id: string;
  org_id: string;
  plan_id: string;
  prediction_snapshot_id?: string | null;
  status: 'pending' | 'partial' | 'complete';
  source: string;
  actual_revenue?: string | null;
  actual_fuel_spend?: string | null;
  actual_tolls?: string | null;
  actual_maintenance?: string | null;
  actual_other_costs?: string | null;
  actual_miles_loaded?: number | null;
  actual_miles_deadhead?: number | null;
  actual_drive_min?: number | null;
  actual_wait_min?: number | null;
  actual: Record<string, any>;
  notes?: string | null;
  recorded_at: string;
  completed_at?: string | null;
}

export interface VarianceDelta {
  field: string;
  predicted?: string | null;
  actual?: string | null;
  delta?: string | null;
  variance_pct?: string | null;
}

export interface OutcomeFlag {
  flag: string;
  severity: 'low' | 'medium' | 'high';
  summary: string;
}

export interface OutcomeReport {
  plan_id: string;
  prediction_snapshot_id?: string | null;
  outcome_id?: string | null;
  outcome_status?: 'pending' | 'partial' | 'complete' | null;
  predicted_summary: Record<string, any>;
  actual_summary: Record<string, any>;
  // Editable actuals for form
  actuals?: {
    revenue?: string | null;
    fuel_spend?: string | null;
    tolls?: string | null;
    maintenance?: string | null;
    other_costs?: string | null;
    miles_loaded?: number | null;
    miles_deadhead?: number | null;
    drive_min?: number | null;
    wait_min?: number | null;
    notes?: string | null;
  };
  deltas: VarianceDelta[];
  flags: OutcomeFlag[];
  explanations: string[];
}

export interface OutcomeSummaryItem {
  plan_id: string;
  outcome_id?: string | null;
  status: string;
  predicted_net_profit?: string | null;
  actual_net_profit?: string | null;
  profit_variance_pct?: string | null;
  predicted_duration_min?: number | null;
  actual_duration_min?: number | null;
  time_variance_pct?: string | null;
  recorded_at?: string | null;
  completed_at?: string | null;
}

// Stratum 4B: Decision Feedback Loop

export interface DecisionCreate {
  plan_id: string;
  decision_type: 'accepted' | 'rejected' | 'modified';
  reason?: string;
}

export interface DecisionResponse {
  id: number;
  org_id: string;
  plan_id: string;
  decision_type: string;
  reason?: string | null;
  outcome_id?: string | null;
  prediction_snapshot_id?: string | null;
  decision_context_snapshot_id?: string | null; // Stratum 5D: Learning Loop
  timestamp: string;
}

// Stratum 5B: Calibration Feedback Loop

export interface PlanEstimates {
  revenue: string;
  costs: string;
  net_profit: string;
  miles: string;
  duration_min: string;
  profit_per_day: string;
}

export interface CalibrationAppliedMeta {
  applied: boolean;
  window_days?: number;
  sample_size?: number;
  confidence?: string;
  bias_pct_by_metric?: Record<string, string>;
  caps_applied?: string[] | null;
  explanation: string[];
}

// Stratum 5A: Prediction Calibration

export interface CalibrationMetric {
  name: string;
  predicted_avg: string;
  actual_avg: string;
  mean_error: string;
  mae: string;
  mean_variance_pct: string;
  direction: 'over' | 'under' | 'accurate';
  sample_size: number;
  worst_case_pct: string;
}

export interface CalibrationReport {
  org_id: string;
  window_days: number;
  computed_at: string;
  sample_size: number;
  accuracy_score: string;
  metrics: CalibrationMetric[];
  insights: string[];
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

// Stratum 5D: Learning Loop — Risk Outcome Report

export interface WarningOutcomeCorrelation {
  warning_kind: string;
  warning_severity: string;
  warning_title: string;
  warning_message: string;
  outcome_verified: boolean;
  outcome_variance_field?: string | null;
  outcome_variance_pct?: string | null;
  assessment: 'correct' | 'false_alarm' | 'partially_correct' | 'unverifiable';
  assessment_explanation: string;
}

export interface DecisionContextSummary {
  captured_at: string;
  trust_score?: number | null;
  trust_label?: string | null;
  trust_warning_count: number;
  copilot_status?: string | null;
  copilot_signal_count: number;
  copilot_high_severity_count: number;
  calibration_sample_size?: number | null;
  calibration_applied?: string | null;
  plan_revenue?: string | null;
  plan_costs?: string | null;
  plan_net_profit?: string | null;
}

export interface OutcomeActualSummary {
  status: string;
  completed_at?: string | null;
  actual_revenue?: string | null;
  actual_costs?: string | null;
  actual_net_profit?: string | null;
  revenue_variance_pct?: string | null;
  costs_variance_pct?: string | null;
  profit_variance_pct?: string | null;
  major_variance_fields: string[];
}

export interface RiskOutcomeReport {
  org_id: string;
  plan_id: string;
  computed_at: string;
  decision_context?: DecisionContextSummary | null;
  pre_decision_warnings: Record<string, any>[];
  outcome_summary?: OutcomeActualSummary | null;
  warning_correlations: WarningOutcomeCorrelation[];
  accuracy_assessment: 'accurate' | 'partially_accurate' | 'inaccurate' | 'insufficient_data';
  accuracy_score: number;
  explanations: string[];
  has_decision_context: boolean;
  has_completed_outcome: boolean;
}
