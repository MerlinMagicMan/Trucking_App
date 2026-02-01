/**
 * TypeScript types for Intelligence APIs (Phase 3C/3D)
 */

export interface IntelMeta {
  org_id: string;
  window: string;
  window_start: string;
  window_end: string;
  source: string;
  computed_at: string | null;
  data_freshness_seconds: number | null;
  sample_size: number | null;
}

export interface LaneIntelData {
  load_count: number;
  rate_p25: number | null;
  rate_p50: number | null;
  rate_p75: number | null;
  rate_p90: number | null;
  avg_rate_per_mile: number | null;
  avg_miles: number | null;
  time_to_cover_p50_minutes: number | null;
  volatility_score: number | null;
}

export interface MarketIntelData {
  active_load_count_avg: number | null;
  new_loads_count: number | null;
  expired_loads_count: number | null;
  reload_depth: number | null;
  market_temperature: string | null;
}

export interface DestinationIntelData {
  reload_probability: number | null;
  avg_time_to_first_reload_minutes: number | null;
  efficiency_score: number | null;
  volatility_score: number | null;
}

export interface NegotiationIntelData {
  position: string | null;
  anchor_usd: number | null;
  suggested_counter_usd: number | null;
  fast_accept_usd: number | null;
  walk_away_usd: number | null;
}

export interface IntelResponse<T> {
  meta: IntelMeta;
  data: T | null;
  explanations: string[];
}
