/**
 * TypeScript types for Copilot API (Phase 4)
 */

export interface CopilotMeta {
  org_id: string;
  plan_id: string;
  as_of: string;
  evaluated_at: string;
  windows: Record<string, string>;
  data_sources: Record<string, string>;
  offline: boolean;
}

export interface Signal {
  kind: 'lane_rate_shift' | 'destination_score_drop' | 'market_temp_downgrade' | 'load_unavailable';
  severity: 'low' | 'medium' | 'high';
  summary: string;
  details: Record<string, any>;
}

export interface Suggestion {
  kind: 'take_now' | 'counter_offer' | 'alternate_destination' | 'add_buffer';
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
