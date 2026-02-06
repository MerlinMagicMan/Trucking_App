import React, { useState, useEffect } from 'react';
import type { Plan } from '../../types/plan';
import type {
  IntelResponse,
  LaneIntelData,
  MarketIntelData,
  DestinationIntelData,
  NegotiationIntelData,
} from '../../types/intel';
import {
  fetchLaneIntel,
  fetchMarketIntel,
  fetchDestinationIntel,
  fetchNegotiationIntel,
} from '../../services/intel';
import type { CopilotResponse, BranchPlanResponse, EvaluationHistoryItem, EvaluationReplayResponse, PlanTrustReport } from '../../types/copilot';
import type { OutcomeReport, RiskOutcomeReport } from '../../types/plan';
import { fetchPlanStatus, branchPlans, fetchEvaluationHistory, replayEvaluation } from '../../services/copilot';
import { fetchOutcomeReport, createDecision, fetchDecisions, fetchTrustReport, fetchRiskOutcomeReport } from '../../services/api';
import type { DecisionResponse } from '../../types/plan';

interface InspectPanelProps {
  plan: Plan | null;
  pinned: boolean;
  onTogglePin: () => void;
  onClose: () => void;
}

type TabId = 'timeline' | 'economics' | 'risk' | 'why' | 'intel' | 'copilot' | 'outcomes';

const formatTime = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

const formatBlockType = (type: string): string =>
  type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

// ---- Timeline Tab ----

const TimelineTab: React.FC<{ plan: Plan }> = ({ plan }) => (
  <div>
    <h3 className="pf-tab-section" style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: 600 }}>
      Complete Timeline
    </h3>
    {plan.time_blocks.map((block, i) => (
      <div key={i} className="pf-timeline-block">
        <div className={`pf-timeline-type pf-timeline-type-${block.block_type}`} />
        <div className="pf-timeline-info">
          <div style={{ fontWeight: 500, color: '#0f172a' }}>
            {formatBlockType(block.block_type)}
          </div>
          <div className="pf-timeline-time">
            {formatTime(block.start_time)}
          </div>
          {block.location_name && (
            <div style={{ color: '#475569', fontSize: '13px' }}>{block.location_name}</div>
          )}
        </div>
        <div className="pf-timeline-duration">
          {Math.floor(block.duration_min / 60)}h {block.duration_min % 60}m
        </div>
      </div>
    ))}
  </div>
);

// ---- Economics Tab (CTO tweak #2: per-load $/mi visible) ----

const EconomicsTab: React.FC<{ plan: Plan }> = ({ plan }) => {
  const [showPerLoad, setShowPerLoad] = useState(true);
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);

  const avgRatePerMile = (() => {
    const totalMiles = plan.loads.reduce((s, l) => s + (l.load.miles || 0) + l.deadhead_miles, 0);
    return totalMiles > 0 ? plan.total_revenue_usd / totalMiles : 0;
  })();

  // Contextual insight
  const profitPerDay = plan.profit_per_day_usd;
  const ratePerMile = avgRatePerMile;

  return (
    <div>
      {/* Contextual insight (CTO tweak #2) */}
      {ratePerMile > 0 && (
        <div className="pf-insight">
          This plan averages ${ratePerMile.toFixed(2)}/mile and earns ${profitPerDay.toFixed(0)}/day.
          {plan.loads.length > 1 && ' Multi-load plans can earn more per day even at lower per-mile rates due to faster reloads.'}
        </div>
      )}

      {/* Per-load metrics (CTO tweak #2: toggle, default ON) */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>Per-Load Breakdown</h3>
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#475569', cursor: 'pointer' }}>
          <input type="checkbox" checked={showPerLoad} onChange={() => setShowPerLoad(!showPerLoad)} />
          Show per-load metrics
        </label>
      </div>

      {showPerLoad && (
        <div className="pf-econ-per-load">
          <table>
            <thead>
              <tr>
                <th>Load</th>
                <th>Revenue</th>
                <th>Miles</th>
                <th>$/Mile</th>
                <th>Deadhead</th>
                <th>Net</th>
              </tr>
            </thead>
            <tbody>
              {plan.loads.map((l, i) => {
                const miles = l.load.miles || 0;
                const rpm = miles > 0 ? l.revenue_usd / miles : 0;
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>
                      {l.load.pickup.city} → {l.load.delivery.city}
                    </td>
                    <td>${l.revenue_usd.toFixed(0)}</td>
                    <td>{miles}</td>
                    <td style={{ fontWeight: 600 }}>${rpm.toFixed(2)}</td>
                    <td>{l.deadhead_miles}mi</td>
                    <td style={{ fontWeight: 600, color: l.net_revenue_usd >= 0 ? '#059669' : '#dc2626' }}>
                      ${l.net_revenue_usd.toFixed(0)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Summary rollup */}
      <div className="pf-tab-section">
        <h3>Financial Summary</h3>
        <div className="pf-econ-row">
          <span>Total Revenue</span>
          <span className="pf-econ-positive" style={{ fontWeight: 600 }}>
            ${plan.total_revenue_usd.toFixed(2)}
          </span>
        </div>
        <div className="pf-econ-row">
          <span>Total Costs</span>
          <span className="pf-econ-negative" style={{ fontWeight: 600 }}>
            -${plan.total_costs_usd.toFixed(2)}
          </span>
        </div>
        <div className="pf-econ-row pf-econ-total">
          <span>Net Profit</span>
          <span style={{ color: plan.net_profit_usd >= 0 ? '#059669' : '#dc2626' }}>
            ${plan.net_profit_usd.toFixed(2)}
          </span>
        </div>
        <div className="pf-econ-row" style={{ borderBottom: 'none' }}>
          <span style={{ fontWeight: 600 }}>Profit / Day</span>
          <span style={{ fontWeight: 700, fontSize: '18px', color: '#059669' }}>
            ${plan.profit_per_day_usd.toFixed(2)}
          </span>
        </div>
      </div>

      {/* All financial events */}
      <div className="pf-tab-section">
        <h3>All Financial Events</h3>
        {plan.financial_events.map((event, i) => (
          <div key={i}>
            <div
              className="pf-econ-row"
              style={{ cursor: event.calculation_details ? 'pointer' : 'default' }}
              onClick={() => event.calculation_details && setExpandedEvent(expandedEvent === i ? null : i)}
            >
              <span>{event.description}</span>
              <span
                style={{ fontWeight: 600 }}
                className={event.amount_usd >= 0 ? 'pf-econ-positive' : 'pf-econ-negative'}
              >
                {event.amount_usd >= 0 ? '+' : ''}${event.amount_usd.toFixed(2)}
              </span>
            </div>
            {expandedEvent === i && event.calculation_details && (
              <div className="pf-econ-details">
                {typeof event.calculation_details === 'string'
                  ? event.calculation_details
                  : JSON.stringify(event.calculation_details, null, 2)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ---- Risk & Confidence Tab ----

const RiskTab: React.FC<{ plan: Plan }> = ({ plan }) => (
  <div>
    <div className="pf-tab-section">
      <h3>Confidence Level</h3>
      <span
        className={`pf-badge pf-badge-${plan.confidence === 'high' ? 'low' : plan.confidence === 'low' ? 'high' : 'medium'}`}
        style={{ fontSize: '14px', padding: '6px 14px' }}
      >
        {plan.confidence.toUpperCase()} CONFIDENCE
      </span>
    </div>

    <div className="pf-tab-section">
      <h3>Risk Signals ({plan.risk_signals.length})</h3>
      {plan.risk_signals.length === 0 ? (
        <p style={{ color: '#059669', fontSize: '14px' }}>No significant risks identified.</p>
      ) : (
        plan.risk_signals.map((risk, i) => (
          <div key={i} className={`pf-risk-card pf-risk-card-${risk.severity}`}>
            <div className="pf-risk-type">
              {risk.severity} — {risk.risk_type.replace(/_/g, ' ')}
            </div>
            <div className="pf-risk-description">{risk.description}</div>
          </div>
        ))
      )}
    </div>

    <div className="pf-tab-section">
      <h3>What Could Go Wrong</h3>
      <ul style={{ paddingLeft: '20px', fontSize: '14px', lineHeight: 1.7, color: '#475569' }}>
        {plan.risk_signals.filter(r => r.severity !== 'low').length === 0 ? (
          <li>No major concerns for this plan.</li>
        ) : (
          plan.risk_signals
            .filter(r => r.severity !== 'low')
            .map((r, i) => <li key={i}>{r.description}</li>)
        )}
      </ul>
    </div>
  </div>
);

// ---- Why This Plan Tab ----

const WhyTab: React.FC<{ plan: Plan }> = ({ plan }) => (
  <div>
    <div className="pf-tab-section">
      <h3>Why This Plan</h3>
      {plan.explanations.map((exp, i) => (
        <div key={i} className="pf-explanation">
          <span className="pf-explanation-number">{i + 1}</span>
          {exp}
        </div>
      ))}
    </div>

    {plan.warnings.length > 0 && (
      <div className="pf-tab-section">
        <h3>Warnings</h3>
        {plan.warnings.map((w, i) => (
          <div key={i} className="pf-warning">{w}</div>
        ))}
      </div>
    )}
  </div>
);

// ---- Intel Tab ----

interface IntelState {
  status: 'idle' | 'loading' | 'offline' | 'loaded';
  lane: IntelResponse<LaneIntelData> | null;
  market: IntelResponse<MarketIntelData> | null;
  destination: IntelResponse<DestinationIntelData> | null;
  negotiation: IntelResponse<NegotiationIntelData> | null;
}

const tempColor = (t: string | null | undefined): string => {
  if (t === 'hot') return '#dc2626';
  if (t === 'cold') return '#2563eb';
  return '#d97706';
};

const scoreColor = (s: number): string => {
  if (s >= 70) return '#059669';
  if (s >= 40) return '#d97706';
  return '#dc2626';
};

const IntelRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="pf-intel-row">
    <span className="pf-intel-label">{label}</span>
    <span className="pf-intel-value">{value}</span>
  </div>
);

const IntelExplanations: React.FC<{ explanations: string[] }> = ({ explanations }) => (
  <div style={{ marginTop: '8px' }}>
    {explanations.map((e, i) => (
      <p key={i} className="pf-intel-offline" style={{ margin: '4px 0' }}>{e}</p>
    ))}
  </div>
);

const IntelTab: React.FC<{ plan: Plan }> = ({ plan }) => {
  const [state, setState] = useState<IntelState>({
    status: 'idle', lane: null, market: null, destination: null, negotiation: null,
  });

  const firstLoad = plan.loads[0]?.load;
  const originGh = firstLoad?.pickup_geohash;
  const destGh = firstLoad?.delivery_geohash;
  const hasGeohash = !!(originGh && destGh);

  useEffect(() => {
    if (!hasGeohash || !originGh || !destGh) return;

    let cancelled = false;
    setState(s => ({ ...s, status: 'loading' }));

    Promise.all([
      fetchLaneIntel(originGh, destGh),
      fetchMarketIntel(destGh),
      fetchDestinationIntel(destGh),
      fetchNegotiationIntel(originGh, destGh, firstLoad.rate_total),
    ]).then(([lane, market, destination, negotiation]) => {
      if (cancelled) return;
      const allFailed = !lane && !market && !destination && !negotiation;
      setState({
        status: allFailed ? 'offline' : 'loaded',
        lane, market, destination, negotiation,
      });
    });

    return () => { cancelled = true; };
  }, [plan.plan_id, hasGeohash, originGh, destGh, firstLoad?.rate_total]);

  if (!hasGeohash) {
    return (
      <div className="pf-tab-section">
        <p className="pf-intel-offline">Intel unavailable — geohash data not present for this load.</p>
      </div>
    );
  }

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="pf-tab-section">
        <p className="pf-intel-offline">Loading intel...</p>
      </div>
    );
  }

  if (state.status === 'offline') {
    return (
      <div className="pf-tab-section">
        <p className="pf-intel-offline">Intel Offline — analytics service unavailable.</p>
      </div>
    );
  }

  const { lane, market, destination, negotiation } = state;

  return (
    <div>
      {/* Lane Intel */}
      <div className="pf-intel-section">
        <h3>Lane Intel</h3>
        {lane?.data ? (
          <>
            <IntelRow
              label="Rate range"
              value={
                <span>
                  ${lane.data.rate_p25?.toFixed(0) ?? '—'} —{' '}
                  <strong>${lane.data.rate_p50?.toFixed(0) ?? '—'}</strong> —{' '}
                  ${lane.data.rate_p75?.toFixed(0) ?? '—'}
                </span>
              }
            />
            {lane.data.time_to_cover_p50_minutes != null && (
              <IntelRow
                label="Time to cover (p50)"
                value={`${Math.floor(lane.data.time_to_cover_p50_minutes / 60)}h ${Math.round(lane.data.time_to_cover_p50_minutes % 60)}m`}
              />
            )}
            {lane.data.avg_rate_per_mile != null && (
              <IntelRow label="Avg $/mile" value={`$${lane.data.avg_rate_per_mile.toFixed(2)}`} />
            )}
            {lane.meta.sample_size != null && (
              <IntelRow label="Sample size" value={lane.meta.sample_size} />
            )}
          </>
        ) : (
          <IntelExplanations explanations={lane?.explanations ?? ['No lane data available.']} />
        )}
      </div>

      {/* Destination Intel */}
      <div className="pf-intel-section">
        <h3>Destination Intel</h3>
        {destination?.data ? (
          <>
            {destination.data.efficiency_score != null && (
              <IntelRow
                label="Efficiency score"
                value={
                  <span style={{ fontWeight: 600, color: scoreColor(destination.data.efficiency_score) }}>
                    {destination.data.efficiency_score.toFixed(0)}/100
                  </span>
                }
              />
            )}
            {destination.data.reload_probability != null && (
              <IntelRow label="Reload probability" value={`${(destination.data.reload_probability * 100).toFixed(0)}%`} />
            )}
            {destination.data.avg_time_to_first_reload_minutes != null && (
              <IntelRow
                label="Avg reload wait"
                value={`${Math.floor(destination.data.avg_time_to_first_reload_minutes / 60)}h ${Math.round(destination.data.avg_time_to_first_reload_minutes % 60)}m`}
              />
            )}
          </>
        ) : (
          <IntelExplanations explanations={destination?.explanations ?? ['No destination data available.']} />
        )}
      </div>

      {/* Market Intel */}
      <div className="pf-intel-section">
        <h3>Market Intel</h3>
        {market?.data ? (
          <>
            {market.data.market_temperature != null && (
              <IntelRow
                label="Temperature"
                value={
                  <span
                    className="pf-intel-badge"
                    style={{ color: '#fff', backgroundColor: tempColor(market.data.market_temperature) }}
                  >
                    {market.data.market_temperature.toUpperCase()}
                  </span>
                }
              />
            )}
            {market.data.reload_depth != null && (
              <IntelRow label="Reload depth" value={market.data.reload_depth.toFixed(2)} />
            )}
            {market.data.active_load_count_avg != null && (
              <IntelRow label="Active loads (avg)" value={market.data.active_load_count_avg.toFixed(0)} />
            )}
          </>
        ) : (
          <IntelExplanations explanations={market?.explanations ?? ['No market data available.']} />
        )}
      </div>

      {/* Negotiation Intel */}
      <div className="pf-intel-section" style={{ borderBottom: 'none' }}>
        <h3>Negotiation Intel</h3>
        {negotiation?.data ? (
          <>
            {negotiation.data.position && (
              <IntelRow
                label="Position"
                value={
                  <span style={{ fontWeight: 600 }}>
                    {negotiation.data.position.replace(/_/g, ' ')}
                  </span>
                }
              />
            )}
            {negotiation.data.suggested_counter_usd != null && (
              <IntelRow label="Suggested counter" value={`$${negotiation.data.suggested_counter_usd.toFixed(0)}`} />
            )}
            {negotiation.data.walk_away_usd != null && (
              <IntelRow label="Walk-away below" value={`$${negotiation.data.walk_away_usd.toFixed(0)}`} />
            )}
          </>
        ) : (
          <IntelExplanations explanations={negotiation?.explanations ?? ['No negotiation data available.']} />
        )}
      </div>
    </div>
  );
};

// ---- Trust Section (reusable) ----

const trustLabelColor = (label: string): { bg: string; text: string } => {
  if (label === 'high') return { bg: '#dcfce7', text: '#166534' };
  if (label === 'medium') return { bg: '#fef3c7', text: '#92400e' };
  if (label === 'low') return { bg: '#fee2e2', text: '#991b1b' };
  return { bg: '#f1f5f9', text: '#64748b' };
};

const TrustSection: React.FC<{ trust: PlanTrustReport | null | undefined; compact?: boolean }> = ({ trust, compact }) => {
  const [showExplanations, setShowExplanations] = useState(false);

  if (trust === undefined) {
    return <p style={{ color: '#94a3b8', fontSize: '12px', fontStyle: 'italic' }}>Loading trust...</p>;
  }

  if (trust === null) {
    return <p style={{ color: '#94a3b8', fontSize: '12px', fontStyle: 'italic' }}>Trust unavailable</p>;
  }

  const { confidence_score, confidence_label, warnings, explanations, meta } = trust;
  const labelStyle = trustLabelColor(confidence_label);

  // Show "Trust building" message for unknown with low sample
  if (confidence_label === 'unknown' && meta.sample_size < 10) {
    return (
      <div style={{ padding: compact ? '0' : '8px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span style={{
            fontSize: '12px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px',
            background: labelStyle.bg, color: labelStyle.text,
          }}>
            BUILDING
          </span>
          <span style={{ fontSize: '12px', color: '#64748b' }}>
            {meta.sample_size}/10 outcomes
          </span>
        </div>
        <p style={{ fontSize: '12px', color: '#64748b', margin: '4px 0' }}>
          Trust building: need more completed outcomes for calibration.
        </p>
      </div>
    );
  }

  const topWarnings = warnings.slice(0, 3);

  return (
    <div style={{ padding: compact ? '0' : '8px 0' }}>
      {/* Score badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span style={{
          fontSize: '13px', fontWeight: 700, padding: '3px 10px', borderRadius: '4px',
          background: labelStyle.bg, color: labelStyle.text,
        }}>
          {confidence_score}/100 {confidence_label.toUpperCase()}
        </span>
        <span style={{ fontSize: '11px', color: '#94a3b8' }}>
          {meta.sample_size} outcomes · {meta.window_days}d
        </span>
      </div>

      {/* Top warnings */}
      {topWarnings.length > 0 && (
        <div style={{ marginBottom: '8px' }}>
          {topWarnings.map((w, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '4px 0', fontSize: '12px',
            }}>
              <span style={{
                fontSize: '10px', fontWeight: 600, padding: '1px 5px', borderRadius: '3px',
                background: w.severity === 'high' ? '#fee2e2' : w.severity === 'medium' ? '#fef3c7' : '#e0e7ff',
                color: w.severity === 'high' ? '#991b1b' : w.severity === 'medium' ? '#92400e' : '#3730a3',
                textTransform: 'uppercase',
              }}>
                {w.severity}
              </span>
              <span style={{ fontWeight: 500, color: '#0f172a' }}>{w.title}</span>
              {!compact && <span style={{ color: '#64748b' }}>— {w.message}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Why expander */}
      {!compact && explanations.length > 0 && (
        <div>
          <button
            onClick={() => setShowExplanations(!showExplanations)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: '11px', color: '#64748b', padding: 0, textDecoration: 'underline',
            }}
            type="button"
          >
            {showExplanations ? 'Hide details' : 'Why this score?'}
          </button>
          {showExplanations && (
            <div style={{ marginTop: '6px', fontSize: '12px', color: '#475569' }}>
              {explanations.map((e, i) => (
                <div key={i} style={{ marginBottom: '2px' }}>· {e}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ---- Copilot Tab ----

const severityColor = (s: string): string => {
  if (s === 'high') return '#dc2626';
  if (s === 'medium') return '#d97706';
  return '#2563eb';
};

const statusPill = (s: string): { bg: string; text: string; label: string } => {
  if (s === 'ok') return { bg: '#dcfce7', text: '#059669', label: 'OK' };
  if (s === 'degraded') return { bg: '#fef3c7', text: '#d97706', label: 'DEGRADED' };
  return { bg: '#f1f5f9', text: '#64748b', label: 'UNKNOWN' };
};

const CopilotTab: React.FC<{ plan: Plan }> = ({ plan }) => {
  const [state, setState] = useState<{ status: 'idle' | 'loading' | 'loaded'; data: CopilotResponse | null }>({
    status: 'idle', data: null,
  });
  const [expandedSignal, setExpandedSignal] = useState<number | null>(null);
  const [expandedSuggestion, setExpandedSuggestion] = useState<number | null>(null);
  const [branchState, setBranchState] = useState<Record<number, { status: 'idle' | 'loading' | 'loaded' | 'error'; data: BranchPlanResponse | null }>>({});
  const [history, setHistory] = useState<EvaluationHistoryItem[]>([]);
  const [replayData, setReplayData] = useState<{ evalId: number; status: 'loading' | 'loaded' | 'error'; data: EvaluationReplayResponse | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', data: null });

    fetchPlanStatus(plan.plan_id).then((result) => {
      if (cancelled) return;
      setState({ status: 'loaded', data: result });
    });

    return () => { cancelled = true; };
  }, [plan.plan_id]);

  // Fetch evaluation history
  useEffect(() => {
    fetchEvaluationHistory(plan.plan_id).then(setHistory);
  }, [plan.plan_id, state.status]); // refetch after new evaluation is persisted

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="pf-tab-section">
        <p className="pf-intel-offline">Evaluating plan...</p>
      </div>
    );
  }

  if (!state.data) {
    return (
      <div className="pf-tab-section">
        <p className="pf-intel-offline">Copilot Offline — could not evaluate plan.</p>
      </div>
    );
  }

  const { data } = state;
  const pill = statusPill(data.status);

  return (
    <div>
      {/* Trust Section */}
      {data.meta.trust && (
        <div className="pf-intel-section">
          <h3 style={{ marginBottom: '8px' }}>Trust Score</h3>
          <TrustSection trust={data.meta.trust} />
        </div>
      )}

      {/* Status */}
      <div className="pf-intel-section">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <h3 style={{ margin: 0 }}>Plan Status</h3>
          <span
            className="pf-intel-badge"
            style={{ backgroundColor: pill.bg, color: pill.text }}
          >
            {pill.label}
          </span>
          {data.meta.offline && (
            <span className="pf-intel-offline" style={{ fontSize: '12px' }}>(offline)</span>
          )}
        </div>
        {data.explanations.map((e, i) => (
          <p key={i} style={{ margin: '4px 0', fontSize: '13px', color: '#475569' }}>{e}</p>
        ))}
      </div>

      {/* Signals */}
      {data.signals.length > 0 && (
        <div className="pf-intel-section">
          <h3>Signals ({data.signals.length})</h3>
          {data.signals.map((signal, i) => (
            <div
              key={i}
              className="pf-copilot-signal"
              style={{ cursor: 'pointer' }}
              onClick={() => setExpandedSignal(expandedSignal === i ? null : i)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  className="pf-intel-badge"
                  style={{ backgroundColor: severityColor(signal.severity), color: '#fff', textTransform: 'uppercase' }}
                >
                  {signal.severity}
                </span>
                <span style={{ fontSize: '13px', color: '#0f172a' }}>{signal.summary}</span>
              </div>
              {expandedSignal === i && Object.keys(signal.details).length > 0 && (
                <div className="pf-copilot-details">
                  {Object.entries(signal.details).map(([k, v]) => (
                    <div key={k} className="pf-intel-row">
                      <span className="pf-intel-label">{k.replace(/_/g, ' ')}</span>
                      <span className="pf-intel-value">
                        {typeof v === 'number' ? (k.includes('usd') ? `$${v.toFixed(2)}` : v.toFixed(2)) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Suggestions */}
      {data.suggestions.length > 0 && (
        <div className="pf-intel-section">
          <h3>Suggestions ({data.suggestions.length})</h3>
          {data.suggestions.map((sug, i) => {
            const bs = branchState[i] || { status: 'idle', data: null };
            const handleBranch = (e: React.MouseEvent) => {
              e.stopPropagation();
              if (bs.status === 'loading') return;
              setBranchState((prev) => ({ ...prev, [i]: { status: 'loading', data: null } }));
              branchPlans({
                plan_id: plan.plan_id,
                suggestion_kind: sug.kind,
                suggestion_data: sug.data,
              }).then((result) => {
                setBranchState((prev) => ({
                  ...prev,
                  [i]: result ? { status: 'loaded', data: result } : { status: 'error', data: null },
                }));
              });
            };

            return (
              <div
                key={i}
                className="pf-copilot-suggestion"
                style={{ cursor: 'pointer' }}
                onClick={() => setExpandedSuggestion(expandedSuggestion === i ? null : i)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span
                    className="pf-intel-badge"
                    style={{ backgroundColor: '#e0e7ff', color: '#4338ca' }}
                  >
                    {sug.kind.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: '13px', fontWeight: 500, color: '#0f172a' }}>{sug.summary}</span>
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>{sug.rationale}</p>
                {expandedSuggestion === i && Object.keys(sug.data).length > 0 && (
                  <div className="pf-copilot-details">
                    {Object.entries(sug.data).filter(([, v]) => v != null).map(([k, v]) => (
                      <div key={k} className="pf-intel-row">
                        <span className="pf-intel-label">{k.replace(/_/g, ' ')}</span>
                        <span className="pf-intel-value">
                          {typeof v === 'number' ? (k.includes('usd') || k.includes('rate') ? `$${v.toFixed(2)}` : v.toFixed(2)) : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Branch plan button */}
                <div style={{ marginTop: '8px' }}>
                  {bs.status === 'idle' && (
                    <button className="pf-copilot-branch-btn" onClick={handleBranch}>
                      Generate Branch Plans
                    </button>
                  )}
                  {bs.status === 'loading' && (
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>Generating...</span>
                  )}
                  {bs.status === 'error' && (
                    <span style={{ fontSize: '12px', color: '#ef4444' }}>Branch generation failed</span>
                  )}
                  {bs.status === 'loaded' && bs.data && (
                    <div className="pf-copilot-branch-results">
                      {bs.data.plans.length === 0 ? (
                        <p style={{ fontSize: '12px', color: '#94a3b8', margin: '4px 0' }}>
                          No feasible branch plans found.
                        </p>
                      ) : (
                        bs.data.plans.map((bp) => (
                          <div key={bp.plan_id} className="pf-copilot-branch-result">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 600, fontSize: '13px' }}>
                                ${bp.profit_per_day_usd.toFixed(0)}/day
                              </span>
                              <span style={{ fontSize: '11px', color: '#64748b' }}>
                                {bp.num_loads} loads &middot; {bp.confidence}
                              </span>
                            </div>
                            <div style={{ fontSize: '12px', color: '#475569', marginTop: '2px' }}>
                              Net ${bp.net_profit_usd.toFixed(0)} &middot; Ends {bp.end_location}
                            </div>
                          </div>
                        ))
                      )}
                      {Object.keys(bs.data.constraint_changes).length > 0 && (
                        <p style={{ fontSize: '11px', color: '#94a3b8', margin: '4px 0 0' }}>
                          Changed: {Object.entries(bs.data.constraint_changes).map(([k, v]) => `${k.replace(/_/g, ' ')}=${v}`).join(', ')}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Evaluation History */}
      <div className="pf-intel-section" style={{ borderBottom: 'none' }}>
        <h3>Evaluation History</h3>
        {history.length === 0 ? (
          <p style={{ fontSize: '12px', color: '#94a3b8', fontStyle: 'italic' }}>No evaluation history yet.</p>
        ) : (
          <>
            {history.slice(0, 10).map((item) => {
              const p = statusPill(item.status);
              const isReplaying = replayData?.evalId === item.id;
              const ts = new Date(item.timestamp).toLocaleString('en-US', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
              });

              return (
                <div key={item.id} className="pf-copilot-history-item">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="pf-intel-badge" style={{ backgroundColor: p.bg, color: p.text, fontSize: '10px' }}>
                      {p.label}
                    </span>
                    <span style={{ fontSize: '12px', color: '#475569' }}>{ts}</span>
                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                      {item.signal_count}s / {item.suggestion_count}r
                    </span>
                    <button
                      className="pf-copilot-branch-btn"
                      style={{ marginLeft: 'auto', fontSize: '11px', padding: '2px 6px' }}
                      onClick={() => {
                        if (isReplaying) return;
                        setReplayData({ evalId: item.id, status: 'loading', data: null });
                        replayEvaluation(item.id).then((res) => {
                          setReplayData(res
                            ? { evalId: item.id, status: 'loaded', data: res }
                            : { evalId: item.id, status: 'error', data: null }
                          );
                        });
                      }}
                    >
                      {isReplaying && replayData?.status === 'loading' ? '...' : 'Replay'}
                    </button>
                  </div>

                  {/* Drift view */}
                  {isReplaying && replayData?.status === 'loaded' && replayData.data && (
                    <div className="pf-copilot-drift">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span className="pf-intel-badge" style={{
                          backgroundColor: statusPill(replayData.data.original.status).bg,
                          color: statusPill(replayData.data.original.status).text,
                          fontSize: '10px',
                        }}>
                          Then: {replayData.data.original.status}
                        </span>
                        <span style={{ fontSize: '12px', color: '#475569' }}>&rarr;</span>
                        <span className="pf-intel-badge" style={{
                          backgroundColor: statusPill(replayData.data.replayed.status).bg,
                          color: statusPill(replayData.data.replayed.status).text,
                          fontSize: '10px',
                        }}>
                          Now: {replayData.data.replayed.status}
                        </span>
                      </div>
                      {replayData.data.drift.new_signals.length > 0 && (
                        <p style={{ fontSize: '11px', color: '#dc2626', margin: '2px 0' }}>
                          New: {replayData.data.drift.new_signals.map((s) => s.kind.replace(/_/g, ' ')).join(', ')}
                        </p>
                      )}
                      {replayData.data.drift.resolved_signals.length > 0 && (
                        <p style={{ fontSize: '11px', color: '#16a34a', margin: '2px 0' }}>
                          Resolved: {replayData.data.drift.resolved_signals.map((s) => s.kind.replace(/_/g, ' ')).join(', ')}
                        </p>
                      )}
                      {replayData.data.drift.severity_changes.length > 0 && (
                        <p style={{ fontSize: '11px', color: '#d97706', margin: '2px 0' }}>
                          Changed: {replayData.data.drift.severity_changes.map((s) => `${s.kind.replace(/_/g, ' ')} ${s.was}→${s.now}`).join(', ')}
                        </p>
                      )}
                      {replayData.data.drift.new_signals.length === 0
                        && replayData.data.drift.resolved_signals.length === 0
                        && replayData.data.drift.severity_changes.length === 0 && (
                        <p style={{ fontSize: '11px', color: '#94a3b8', margin: '2px 0' }}>No drift detected.</p>
                      )}
                    </div>
                  )}
                  {isReplaying && replayData?.status === 'error' && (
                    <p style={{ fontSize: '11px', color: '#ef4444', margin: '4px 0' }}>Replay failed.</p>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
};

// ---- Outcomes Tab ----

const OutcomesTab: React.FC<{ plan: Plan }> = ({ plan }) => {
  const [report, setReport] = useState<OutcomeReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [trust, setTrust] = useState<PlanTrustReport | null | undefined>(undefined);
  const [riskReport, setRiskReport] = useState<RiskOutcomeReport | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setDecision(null);
    setTrust(undefined);
    setRiskReport(null);
    Promise.all([
      fetchOutcomeReport(plan.plan_id).catch(() => null),
      fetchDecisions(plan.plan_id),
      fetchTrustReport(plan.plan_id).catch(() => null),
      fetchRiskOutcomeReport(plan.plan_id).catch(() => null),
    ]).then(([rpt, decisions, trustRpt, risk]) => {
      setReport(rpt);
      setTrust(trustRpt);
      setRiskReport(risk);
      if (decisions.length > 0) {
        setDecision(decisions[0]);
      }
    }).finally(() => setLoading(false));
  }, [plan.plan_id]);

  const handleAccept = async () => {
    setDeciding(true);
    setError(null);
    try {
      const d = await createDecision({ plan_id: plan.plan_id, decision_type: 'accepted' });
      setDecision(d);
      const r = await fetchOutcomeReport(plan.plan_id);
      setReport(r);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to accept plan');
    } finally {
      setDeciding(false);
    }
  };

  const handleReject = async () => {
    const reason = window.prompt('Reason for rejection (optional):');
    if (reason === null) return; // User cancelled prompt
    setDeciding(true);
    setError(null);
    try {
      const d = await createDecision({
        plan_id: plan.plan_id,
        decision_type: 'rejected',
        reason: reason || undefined,
      });
      setDecision(d);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to reject plan');
    } finally {
      setDeciding(false);
    }
  };

  if (loading) return <div style={{ color: '#94a3b8', padding: '16px' }}>Loading outcomes...</div>;

  // Show decision buttons if no decision or no outcome yet
  const hasOutcome = !!report;
  const lastDecisionType = decision?.decision_type;

  if (!hasOutcome && lastDecisionType !== 'accepted') {
    return (
      <div style={{ padding: '16px' }}>
        {lastDecisionType === 'rejected' && (
          <div style={{
            display: 'inline-block', padding: '3px 10px', borderRadius: '4px',
            background: '#fef2f2', color: '#991b1b', fontSize: '13px', fontWeight: 600,
            marginBottom: '12px',
          }}>
            Rejected{decision?.reason ? `: ${decision.reason}` : ''}
          </div>
        )}
        {!lastDecisionType && (
          <p style={{ color: '#64748b', marginBottom: '12px' }}>
            Accept this plan to start tracking actuals vs predictions.
          </p>
        )}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn btn-sm"
            onClick={handleAccept}
            disabled={deciding}
            type="button"
            style={{ background: '#16a34a', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: '4px', cursor: 'pointer' }}
          >
            {deciding ? 'Accepting...' : 'Accept Plan'}
          </button>
          <button
            className="btn btn-sm"
            onClick={handleReject}
            disabled={deciding}
            type="button"
            style={{ background: '#dc2626', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: '4px', cursor: 'pointer' }}
          >
            Reject
          </button>
        </div>
        {error && <p style={{ color: '#dc2626', fontSize: '13px', marginTop: '8px' }}>{error}</p>}
      </div>
    );
  }

  // Show accepted badge if accepted
  if (!report && lastDecisionType === 'accepted') {
    return (
      <div style={{ padding: '16px' }}>
        <div style={{
          display: 'inline-block', padding: '3px 10px', borderRadius: '4px',
          background: '#f0fdf4', color: '#166534', fontSize: '13px', fontWeight: 600,
          marginBottom: '8px',
        }}>
          Accepted — Tracking
        </div>
        <p style={{ color: '#64748b', fontSize: '13px' }}>
          Prediction snapshot created. Outcome report will appear once data is available.
        </p>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div>
      {lastDecisionType === 'accepted' && (
        <div style={{
          display: 'inline-block', padding: '3px 10px', borderRadius: '4px',
          background: '#f0fdf4', color: '#166534', fontSize: '13px', fontWeight: 600,
          marginBottom: '8px',
        }}>
          Accepted — Tracking
        </div>
      )}

      {/* Trust section in outcomes */}
      {trust !== undefined && (
        <div style={{ marginBottom: '16px', padding: '12px', background: '#f8fafc', borderRadius: '6px' }}>
          <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 8px', color: '#475569' }}>Prediction Trust</h4>
          <TrustSection trust={trust} compact />
        </div>
      )}
      <h3 style={{ margin: '0 0 12px', fontSize: '16px', fontWeight: 600 }}>Predicted vs Actual</h3>

      {/* Deltas table */}
      {report.deltas.length > 0 && (
        <table className="data-table" style={{ marginBottom: '16px' }}>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Predicted</th>
              <th>Actual</th>
              <th>Delta</th>
              <th>Variance</th>
            </tr>
          </thead>
          <tbody>
            {report.deltas.map((d, i) => {
              const varNum = d.variance_pct ? parseFloat(d.variance_pct) : null;
              let varColor = '#64748b';
              if (varNum !== null) {
                const abs = Math.abs(varNum);
                if (abs > 25) varColor = '#dc2626';
                else if (abs > 10) varColor = '#d97706';
                else varColor = '#16a34a';
              }
              return (
                <tr key={i}>
                  <td style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                    {d.field.replace(/_/g, ' ')}
                  </td>
                  <td className="td-mono">{d.predicted != null ? (d.field.includes('min') ? `${d.predicted} min` : `$${d.predicted}`) : '—'}</td>
                  <td className="td-mono">{d.actual != null ? (d.field.includes('min') ? `${d.actual} min` : `$${d.actual}`) : '—'}</td>
                  <td className="td-mono">{d.delta != null ? (d.field.includes('min') ? `${d.delta} min` : `$${d.delta}`) : '—'}</td>
                  <td style={{ color: varColor, fontWeight: 600 }}>
                    {d.variance_pct != null ? `${parseFloat(d.variance_pct) > 0 ? '+' : ''}${d.variance_pct}%` : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {/* Flags */}
      {report.flags.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 8px' }}>Flags</h4>
          {report.flags.map((f, i) => (
            <div key={i} style={{
              display: 'flex', gap: '8px', alignItems: 'center',
              padding: '6px 10px', marginBottom: '4px', borderRadius: '4px',
              background: f.severity === 'high' ? '#fef2f2' : f.severity === 'medium' ? '#fffbeb' : '#f0fdf4',
              fontSize: '13px',
            }}>
              <span style={{
                fontSize: '11px', fontWeight: 600, padding: '1px 5px', borderRadius: '3px',
                background: f.severity === 'high' ? '#fee2e2' : f.severity === 'medium' ? '#fef3c7' : '#dcfce7',
                color: f.severity === 'high' ? '#991b1b' : f.severity === 'medium' ? '#92400e' : '#166534',
              }}>{f.severity}</span>
              <span>{f.summary}</span>
            </div>
          ))}
        </div>
      )}

      {/* Explanations */}
      {report.explanations.length > 0 && (
        <div>
          <h4 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 8px' }}>Analysis</h4>
          {report.explanations.map((e, i) => (
            <p key={i} style={{ fontSize: '13px', color: '#475569', margin: '0 0 4px' }}>{e}</p>
          ))}
        </div>
      )}

      {/* Risk Outcome Report - Learning Loop */}
      {riskReport && riskReport.has_decision_context && (
        <div style={{ marginTop: '20px', padding: '12px', background: '#f8fafc', borderRadius: '6px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 12px', color: '#334155' }}>
            Learning Loop: What We Knew vs What Happened
          </h4>

          {/* Accuracy badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <span style={{
              fontSize: '12px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px',
              background: riskReport.accuracy_assessment === 'accurate' ? '#dcfce7'
                : riskReport.accuracy_assessment === 'partially_accurate' ? '#fef3c7'
                : riskReport.accuracy_assessment === 'inaccurate' ? '#fee2e2' : '#f1f5f9',
              color: riskReport.accuracy_assessment === 'accurate' ? '#166534'
                : riskReport.accuracy_assessment === 'partially_accurate' ? '#92400e'
                : riskReport.accuracy_assessment === 'inaccurate' ? '#991b1b' : '#64748b',
            }}>
              {riskReport.accuracy_score}/100 {riskReport.accuracy_assessment.replace(/_/g, ' ').toUpperCase()}
            </span>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>
              Warning accuracy
            </span>
          </div>

          {/* Decision context summary */}
          {riskReport.decision_context && (
            <div style={{ marginBottom: '12px' }}>
              <h5 style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', margin: '0 0 6px' }}>
                At Decision Time
              </h5>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', fontSize: '12px' }}>
                {riskReport.decision_context.trust_label && (
                  <span style={{
                    padding: '2px 6px', borderRadius: '3px',
                    background: riskReport.decision_context.trust_label === 'high' ? '#dcfce7'
                      : riskReport.decision_context.trust_label === 'medium' ? '#fef3c7' : '#fee2e2',
                    color: riskReport.decision_context.trust_label === 'high' ? '#166534'
                      : riskReport.decision_context.trust_label === 'medium' ? '#92400e' : '#991b1b',
                  }}>
                    Trust: {riskReport.decision_context.trust_score}/100
                  </span>
                )}
                <span style={{ color: '#64748b' }}>
                  {riskReport.decision_context.trust_warning_count} warnings
                </span>
                {riskReport.decision_context.plan_net_profit && (
                  <span style={{ color: '#64748b' }}>
                    Predicted: ${riskReport.decision_context.plan_net_profit}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Warning correlations */}
          {riskReport.warning_correlations.length > 0 && (
            <div style={{ marginBottom: '12px' }}>
              <h5 style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', margin: '0 0 6px' }}>
                Warning Outcomes
              </h5>
              {riskReport.warning_correlations.slice(0, 5).map((c, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  padding: '4px 0', fontSize: '12px', borderBottom: '1px solid #e2e8f0',
                }}>
                  <span style={{
                    fontSize: '10px', fontWeight: 600, padding: '1px 5px', borderRadius: '3px',
                    background: c.assessment === 'correct' ? '#dcfce7'
                      : c.assessment === 'false_alarm' ? '#fee2e2'
                      : c.assessment === 'partially_correct' ? '#fef3c7' : '#f1f5f9',
                    color: c.assessment === 'correct' ? '#166534'
                      : c.assessment === 'false_alarm' ? '#991b1b'
                      : c.assessment === 'partially_correct' ? '#92400e' : '#64748b',
                    textTransform: 'uppercase',
                    minWidth: '55px',
                    textAlign: 'center',
                  }}>
                    {c.assessment === 'correct' ? '✓' : c.assessment === 'false_alarm' ? '✗' : '~'}
                  </span>
                  <span style={{ fontWeight: 500, color: '#334155' }}>{c.warning_title}</span>
                  {c.outcome_variance_pct && (
                    <span style={{ color: '#64748b', marginLeft: 'auto' }}>
                      {c.outcome_variance_field}: {c.outcome_variance_pct}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Learning explanations */}
          {riskReport.explanations.length > 0 && (
            <div>
              {riskReport.explanations.slice(0, 3).map((e, i) => (
                <p key={i} style={{ fontSize: '11px', color: '#64748b', margin: '0 0 2px' }}>
                  · {e}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ---- Inline Panel (desktop tri-pane) ----

interface InspectPanelInlineProps {
  plan: Plan;
  onClose: () => void;
}

export const InspectPanelInline: React.FC<InspectPanelInlineProps> = ({ plan, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabId>('economics');

  // ESC to close
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Get route name for header
  const routeName = (() => {
    if (plan.loads.length === 0) return 'Plan Details';
    const cities = [plan.loads[0].load.pickup.city];
    plan.loads.forEach(l => cities.push(l.load.delivery.city));
    return cities.join(' → ');
  })();

  return (
    <div className="pf-inspect-inline">
      <div className="pf-panel-inline">
        <div className="pf-panel-header">
          <h2>{routeName}</h2>
          <button className="pf-panel-close" onClick={onClose} type="button" title="Close">
            &times;
          </button>
        </div>

        <nav className="pf-panel-tabs">
          {([
            ['economics', '$'],
            ['timeline', 'Time'],
            ['copilot', 'AI'],
            ['intel', 'Intel'],
            ['risk', 'Risk'],
            ['outcomes', 'Track'],
            ['why', 'Why'],
          ] as [TabId, string][]).map(([id, label]) => (
            <button
              key={id}
              className={`pf-panel-tab ${activeTab === id ? 'active' : ''}`}
              onClick={() => setActiveTab(id)}
              type="button"
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="pf-panel-body">
          {activeTab === 'timeline' && <TimelineTab plan={plan} />}
          {activeTab === 'economics' && <EconomicsTab plan={plan} />}
          {activeTab === 'risk' && <RiskTab plan={plan} />}
          {activeTab === 'why' && <WhyTab plan={plan} />}
          {activeTab === 'intel' && <IntelTab plan={plan} />}
          {activeTab === 'copilot' && <CopilotTab plan={plan} />}
          {activeTab === 'outcomes' && <OutcomesTab plan={plan} />}
        </div>
      </div>
    </div>
  );
};

// ---- Main Panel (overlay mode - mobile only) ----

export const InspectPanel: React.FC<InspectPanelProps> = ({ plan, pinned, onTogglePin, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabId>('timeline');
  const isOpen = plan !== null;

  // ESC to close (unless pinned)
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !pinned) onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose, pinned]);

  return (
    <>
      {/* Overlay (not shown when pinned) */}
      {!pinned && (
        <div
          className={`pf-panel-overlay ${isOpen ? 'open' : ''}`}
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div className={`pf-panel ${isOpen ? 'open' : ''}`}>
        {plan && (
          <>
            <div className="pf-panel-header">
              <h2>Plan Details</h2>
              <div className="pf-panel-header-actions">
                <button
                  className={`pf-panel-pin ${pinned ? 'pinned' : ''}`}
                  onClick={onTogglePin}
                  title={pinned ? 'Unpin panel' : 'Pin panel open'}
                  type="button"
                >
                  {pinned ? 'Pinned' : 'Pin'}
                </button>
                <button className="pf-panel-close" onClick={onClose} type="button">
                  &times;
                </button>
              </div>
            </div>

            <nav className="pf-panel-tabs">
              {([
                ['timeline', 'Timeline'],
                ['economics', 'Economics'],
                ['risk', 'Risk'],
                ['why', 'Why This Plan'],
                ['intel', 'Intel'],
                ['copilot', 'Copilot'],
                ['outcomes', 'Outcomes'],
              ] as [TabId, string][]).map(([id, label]) => (
                <button
                  key={id}
                  className={`pf-panel-tab ${activeTab === id ? 'active' : ''}`}
                  onClick={() => setActiveTab(id)}
                  type="button"
                >
                  {label}
                </button>
              ))}
            </nav>

            <div className="pf-panel-body">
              {activeTab === 'timeline' && <TimelineTab plan={plan} />}
              {activeTab === 'economics' && <EconomicsTab plan={plan} />}
              {activeTab === 'risk' && <RiskTab plan={plan} />}
              {activeTab === 'why' && <WhyTab plan={plan} />}
              {activeTab === 'intel' && <IntelTab plan={plan} />}
              {activeTab === 'copilot' && <CopilotTab plan={plan} />}
              {activeTab === 'outcomes' && <OutcomesTab plan={plan} />}
            </div>
          </>
        )}
      </div>
    </>
  );
};
