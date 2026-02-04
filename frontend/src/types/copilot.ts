/**
 * TypeScript types for Copilot API (Phase 4 + 4.1)
 */

// Stratum 5C: Trust Layer

export type ConfidenceLabel = 'high' | 'medium' | 'low' | 'unknown';
export type WarningSeverity = 'low' | 'medium' | 'high';

export interface TrustMeta {
  org_id: string;
  plan_id: string;
  computed_at: string;
  window_days: number;
  offline: boolean;
  sample_size: number;
  profile_confidence: string;
  volatility_pct: Record<string, string>;
  used_calibrated: boolean;
}

export interface RiskWarning {
  kind: string;
  severity: WarningSeverity;
  title: string;
  message: string;
  suggested_action?: string | null;
  details: Record<string, any>;
}

export interface PlanTrustReport {
  confidence_score: number;
  confidence_label: ConfidenceLabel;
  warnings: RiskWarning[];
  explanations: string[];
  meta: TrustMeta;
}

export interface CopilotMeta {
  org_id: string;
  plan_id: string;
  as_of: string;
  evaluated_at: string;
  windows: Record<string, string>;
  data_sources: Record<string, string>;
  offline: boolean;
  trust?: PlanTrustReport | null;
}

export interface Signal {
  kind: 'lane_rate_shift' | 'destination_score_drop' | 'market_temp_downgrade' | 'load_unavailable';
  severity: 'low' | 'medium' | 'high';
  summary: string;
  details: Record<string, any>;
}

export interface Suggestion {
  kind: 'take_now' | 'counter_offer' | 'alternate_destination' | 'add_buffer' | 'manual_review';
  summary: string;
  rationale: string;
  data: Record<string, any>;
}

export interface CopilotResponse {
  meta: CopilotMeta;
  status: 'ok' | 'degraded' | 'unknown';
  signals: Signal[];
  suggestions: Suggestion[];
  explanations: string[];
}

// Phase 4.1: Branch Plans

export interface BranchPlanRequest {
  plan_id: string;
  suggestion_kind: string;
  suggestion_data?: Record<string, any>;
  max_plans?: number;
}

export interface BranchPlanSummary {
  plan_id: string;
  num_loads: number;
  profit_per_day_usd: number;
  net_profit_usd: number;
  total_revenue_usd: number;
  total_costs_usd: number;
  end_location: string;
  confidence: string;
  plan_score: number;
}

export interface BranchPlanResponse {
  parent_plan_id: string;
  suggestion_applied: string;
  constraint_changes: Record<string, any>;
  plans: BranchPlanSummary[];
  evaluation_id?: number | null;
  warnings: string[];
}

// Phase 4.2: Evaluation History + Replay

export interface EvaluationHistoryItem {
  id: number;
  plan_id: string;
  status: 'ok' | 'degraded' | 'unknown';
  signal_count: number;
  suggestion_count: number;
  timestamp: string;
  windows: Record<string, string>;
  data_sources: Record<string, string>;
}

export interface DriftSummary {
  new_signals: Array<{ kind: string; count: number; severity: string }>;
  resolved_signals: Array<{ kind: string; count: number }>;
  severity_changes: Array<{ kind: string; was: string; now: string }>;
}

export interface EvaluationReplayResponse {
  evaluation_id: number;
  plan_id: string;
  original: CopilotResponse;
  replayed: CopilotResponse;
  drift: DriftSummary;
  original_timestamp: string;
  replayed_at: string;
}
