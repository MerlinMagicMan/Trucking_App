/**
 * IntelPage - Lane/Market/Destination intelligence (PREVIEW-001)
 * Premium feature: query intel endpoints for lane analytics
 */
import React, { useState, useEffect } from 'react';
import { useEntitlement } from '../hooks/useEntitlement';
import { PreviewBadge } from '../components/shared/PreviewBadge';
import { UpgradeCTA } from '../components/shared/UpgradeCTA';
import { getDataClient, isDemoActive } from '../services/dataClient';
import type {
  IntelResponse,
  LaneIntelData,
  MarketIntelData,
  DestinationIntelData,
  NegotiationIntelData,
} from '../types/intel';
import '../styles/preview.css';

type LoadState = 'idle' | 'loading' | 'loaded' | 'offline';

// Sample geohashes for quick testing
const SAMPLE_LANES = [
  { label: 'Chicago → Dallas', origin: '9q5', dest: '9v6' },
  { label: 'Atlanta → Miami', origin: 'djq', dest: 'dhw' },
  { label: 'LA → Phoenix', origin: '9q5', dest: '9tb' },
];

export const IntelPage: React.FC = () => {
  const { canAccess, isPremium } = useEntitlement();
  // Demo mode: auto-populate with first sample lane for one-click testing
  const demoMode = isDemoActive();
  const [origin, setOrigin] = useState(demoMode ? SAMPLE_LANES[0].origin : '');
  const [destination, setDestination] = useState(demoMode ? SAMPLE_LANES[0].dest : '');
  const [loadState, setLoadState] = useState<LoadState>('idle');

  const [laneData, setLaneData] = useState<IntelResponse<LaneIntelData> | null>(null);
  const [marketData, setMarketData] = useState<IntelResponse<MarketIntelData> | null>(null);
  const [destData, setDestData] = useState<IntelResponse<DestinationIntelData> | null>(null);
  const [negotiationData, setNegotiationData] = useState<IntelResponse<NegotiationIntelData> | null>(null);

  const handleSearch = async (originGh?: string, destGh?: string) => {
    const o = originGh ?? origin;
    const d = destGh ?? destination;
    if (!o || !d) return;

    setLoadState('loading');
    try {
      const client = getDataClient();
      const [lane, market, dest, nego] = await Promise.all([
        client.getLaneIntel(o, d),
        client.getMarketIntel(o),
        client.getDestinationIntel(d),
        client.getNegotiationIntel(o, d, 2500),
      ]);

      setLaneData(lane);
      setMarketData(market);
      setDestData(dest);
      setNegotiationData(nego);
      setLoadState('loaded');
    } catch {
      setLoadState('offline');
    }
  };

  // Demo mode: auto-fetch on load for immediate one-click demo experience
  useEffect(() => {
    if (demoMode && canAccess('intel') && origin && destination && loadState === 'idle') {
      handleSearch(origin, destination);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoMode, canAccess('intel')]);

  const handleSampleClick = (sample: { origin: string; dest: string }) => {
    setOrigin(sample.origin);
    setDestination(sample.dest);
  };

  return (
    <div className="page-container" style={{ maxWidth: '1400px' }}>
      <div className="preview-page-header">
        <div>
          <h1>Intel</h1>
          <p className="preview-page-subtitle">Lane, market, and destination analytics</p>
        </div>
        <PreviewBadge variant={isPremium ? 'preview' : 'premium'} />
      </div>

      {!canAccess('intel') ? (
        <UpgradeCTA
          feature="Intel"
          description="Access real-time lane rates, market conditions, and destination analytics."
        />
      ) : (
        <div className="preview-layout">
          {/* Sidebar: Search */}
          <div className="preview-sidebar">
            <div className="preview-section-header">Lane Search</div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#475569', marginBottom: '4px' }}>
                Origin Geohash
              </label>
              <input
                type="text"
                className="preview-search-input"
                style={{ width: '100%', marginBottom: '12px' }}
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                placeholder="e.g., 9q5"
              />

              <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#475569', marginBottom: '4px' }}>
                Destination Geohash
              </label>
              <input
                type="text"
                className="preview-search-input"
                style={{ width: '100%', marginBottom: '16px' }}
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                placeholder="e.g., 9v6"
              />

              <button
                className="preview-search-btn"
                style={{ width: '100%' }}
                onClick={() => handleSearch()}
                disabled={!origin || !destination || loadState === 'loading'}
              >
                {loadState === 'loading' ? 'Loading...' : 'Search'}
              </button>
            </div>

            <div className="preview-section-header" style={{ marginTop: '24px' }}>Quick Picks</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {SAMPLE_LANES.map((sample, i) => (
                <button
                  key={i}
                  onClick={() => handleSampleClick(sample)}
                  style={{
                    padding: '10px 12px',
                    backgroundColor: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '6px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    fontSize: '13px',
                    color: '#334155',
                  }}
                >
                  {sample.label}
                </button>
              ))}
            </div>
          </div>

          {/* Main: Results */}
          <div className="preview-main">
            {loadState === 'idle' ? (
              <div className="preview-empty">
                <h3>Enter a Lane</h3>
                <p>Search for origin and destination geohashes to view intel</p>
              </div>
            ) : loadState === 'loading' ? (
              <div className="preview-loading">Fetching intel data...</div>
            ) : loadState === 'offline' ? (
              <div className="preview-offline">
                Intel service unavailable. The backend may be offline.
              </div>
            ) : (
              <div>
                {/* Lane Intel */}
                <IntelSection title="Lane Intelligence" data={laneData?.data}>
                  {laneData?.data && (
                    <div className="preview-metrics">
                      <MetricCard label="Load Count" value={laneData.data.load_count} />
                      <MetricCard label="Rate P50" value={formatCurrency(laneData.data.rate_p50)} />
                      <MetricCard label="Rate P75" value={formatCurrency(laneData.data.rate_p75)} />
                      <MetricCard label="Avg $/Mile" value={formatCurrency(laneData.data.avg_rate_per_mile)} />
                      <MetricCard label="Avg Miles" value={laneData.data.avg_miles?.toFixed(0) || 'N/A'} />
                      <MetricCard label="TTC (P50)" value={formatMinutes(laneData.data.time_to_cover_p50_minutes)} />
                    </div>
                  )}
                </IntelSection>

                {/* Market Intel */}
                <IntelSection title="Market Intelligence" data={marketData?.data}>
                  {marketData?.data && (
                    <div className="preview-metrics">
                      <MetricCard label="Active Loads" value={marketData.data.active_load_count_avg?.toFixed(0) || 'N/A'} />
                      <MetricCard label="New Loads" value={marketData.data.new_loads_count || 'N/A'} />
                      <MetricCard label="Expired" value={marketData.data.expired_loads_count || 'N/A'} />
                      <MetricCard label="Reload Depth" value={marketData.data.reload_depth?.toFixed(1) || 'N/A'} />
                      <MetricCard
                        label="Temperature"
                        value={marketData.data.market_temperature || 'N/A'}
                        valueClass={getTempClass(marketData.data.market_temperature)}
                      />
                    </div>
                  )}
                </IntelSection>

                {/* Destination Intel */}
                <IntelSection title="Destination Intelligence" data={destData?.data}>
                  {destData?.data && (
                    <div className="preview-metrics">
                      <MetricCard
                        label="Reload Probability"
                        value={destData.data.reload_probability != null ? `${(destData.data.reload_probability * 100).toFixed(0)}%` : 'N/A'}
                      />
                      <MetricCard
                        label="Time to Reload"
                        value={formatMinutes(destData.data.avg_time_to_first_reload_minutes)}
                      />
                      <MetricCard
                        label="Efficiency Score"
                        value={destData.data.efficiency_score?.toFixed(1) || 'N/A'}
                      />
                    </div>
                  )}
                </IntelSection>

                {/* Negotiation Intel */}
                <IntelSection title="Negotiation Intelligence" data={negotiationData?.data}>
                  {negotiationData?.data && (
                    <div className="preview-metrics">
                      <MetricCard label="Position" value={negotiationData.data.position || 'N/A'} />
                      <MetricCard label="Anchor" value={formatCurrency(negotiationData.data.anchor_usd)} />
                      <MetricCard label="Counter Offer" value={formatCurrency(negotiationData.data.suggested_counter_usd)} />
                      <MetricCard label="Fast Accept" value={formatCurrency(negotiationData.data.fast_accept_usd)} />
                      <MetricCard label="Walk Away" value={formatCurrency(negotiationData.data.walk_away_usd)} />
                    </div>
                  )}
                </IntelSection>

                {/* Explanations */}
                {laneData?.explanations && laneData.explanations.length > 0 && (
                  <div className="preview-section">
                    <div className="preview-section-header">Analysis Notes</div>
                    <ul className="preview-insights">
                      {laneData.explanations.map((exp, i) => (
                        <li key={i} className="preview-insight info">{exp}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

interface IntelSectionProps {
  title: string;
  data: any;
  children: React.ReactNode;
}

const IntelSection: React.FC<IntelSectionProps> = ({ title, data, children }) => (
  <div className="preview-section">
    <div className="preview-section-header">{title}</div>
    {data ? children : (
      <div style={{ padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px', color: '#64748b', fontSize: '13px' }}>
        No data available for this query.
      </div>
    )}
  </div>
);

interface MetricCardProps {
  label: string;
  value: string | number | null | undefined;
  valueClass?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, valueClass }) => (
  <div className="preview-metric-card">
    <div className="preview-metric-label">{label}</div>
    <div className={`preview-metric-value ${valueClass || ''}`} style={{ fontSize: '20px' }}>
      {value ?? 'N/A'}
    </div>
  </div>
);

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatMinutes(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  if (value < 60) return `${value.toFixed(0)} min`;
  return `${(value / 60).toFixed(1)} hrs`;
}

function getTempClass(temp: string | null | undefined): string {
  if (!temp) return '';
  const lower = temp.toLowerCase();
  if (lower === 'hot') return 'red';
  if (lower === 'warm') return 'amber';
  if (lower === 'cold') return 'green';
  return '';
}

export default IntelPage;
