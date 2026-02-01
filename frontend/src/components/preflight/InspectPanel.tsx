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
import type { CopilotResponse } from '../../types/copilot';
import { fetchPlanStatus } from '../../services/copilot';

interface InspectPanelProps {
  plan: Plan | null;
  pinned: boolean;
  onTogglePin: () => void;
  onClose: () => void;
}

type TabId = 'timeline' | 'economics' | 'risk' | 'why' | 'intel' | 'copilot';

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

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', data: null });

    fetchPlanStatus(plan.plan_id).then((result) => {
      if (cancelled) return;
      setState({ status: 'loaded', data: result });
    });

    return () => { cancelled = true; };
  }, [plan.plan_id]);

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
        <div className="pf-intel-section" style={{ borderBottom: 'none' }}>
          <h3>Suggestions ({data.suggestions.length})</h3>
          {data.suggestions.map((sug, i) => (
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
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ---- Main Panel ----

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
            </div>
          </>
        )}
      </div>
    </>
  );
};
