import React, { useState } from 'react';
import type { PreflightPreferences, HOSSnapshot } from '../../types/plan';
import { CsvUpload } from './CsvUpload';

interface PreflightSetupProps {
  onSubmit: (prefs: PreflightPreferences) => void;
  loading?: boolean;
  lastUpdated?: string | null;
  planCount?: number;
  loadsAnalyzed?: number;
}

const DEFAULT_HOS: HOSSnapshot = {
  drive_remaining_min: 660,
  on_duty_remaining_min: 840,
  cycle_remaining_min: 4200,
};

const formatMin = (min: number): string => {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}:${String(m).padStart(2, '0')}` : `${h}:00`;
};

export const PreflightSetup: React.FC<PreflightSetupProps> = ({
  onSubmit, loading = false, lastUpdated, planCount, loadsAnalyzed,
}) => {
  const [lat, setLat] = useState(35.4676);
  const [lng, setLng] = useState(-97.5164);
  const [horizon, setHorizon] = useState<7 | 10 | 14>(7);
  const [preferRegions, setPreferRegions] = useState('');
  const [avoidRegions, setAvoidRegions] = useState('');
  const [homeTimeDays, setHomeTimeDays] = useState('');
  const [maxDeadhead, setMaxDeadhead] = useState('');
  const [riskTolerance, setRiskTolerance] = useState<'low' | 'medium' | 'high'>('medium');
  const [hos, setHos] = useState<HOSSnapshot>({ ...DEFAULT_HOS });
  const [editHos, setEditHos] = useState(false);
  const [csvCount, setCsvCount] = useState(0);
  const [collapsed, setCollapsed] = useState(false);

  const handleSubmit = () => {
    const prefs: PreflightPreferences = {
      current_lat: lat,
      current_lng: lng,
      planning_horizon_days: horizon,
      hos,
      risk_tolerance: riskTolerance,
    };
    if (preferRegions.trim()) prefs.prefer_regions = preferRegions.split(',').map(s => s.trim()).filter(Boolean);
    if (avoidRegions.trim()) prefs.avoid_regions = avoidRegions.split(',').map(s => s.trim()).filter(Boolean);
    if (homeTimeDays) prefs.home_time_target_days = parseInt(homeTimeDays, 10);
    if (maxDeadhead) prefs.max_deadhead_miles = parseInt(maxDeadhead, 10);
    onSubmit(prefs);
  };

  return (
    <div className={`pf-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="pf-sidebar-header">
        <h2>Planning</h2>
        <button className="pf-sidebar-toggle" onClick={() => setCollapsed(!collapsed)} type="button" title={collapsed ? 'Expand' : 'Collapse'}>
          {collapsed ? '»' : '«'}
        </button>
      </div>

      {!collapsed && (
        <>
          <div className="pf-sidebar-body">
            {/* Location */}
            <div className="pf-field">
              <span className="pf-field-label">Location</span>
              <div className="pf-input-row">
                <input className="pf-input" type="number" step="0.0001" value={lat} onChange={e => setLat(parseFloat(e.target.value) || 0)} placeholder="Lat" />
                <input className="pf-input" type="number" step="0.0001" value={lng} onChange={e => setLng(parseFloat(e.target.value) || 0)} placeholder="Lng" />
              </div>
              <p className="pf-hint">OKC: 35.4676, -97.5164</p>
            </div>

            {/* Horizon */}
            <div className="pf-field">
              <span className="pf-field-label">Horizon</span>
              <div className="pf-horizon-buttons">
                {([7, 10, 14] as const).map(d => (
                  <button key={d} className={`pf-horizon-btn ${horizon === d ? 'active' : ''}`} onClick={() => setHorizon(d)} type="button">{d}d</button>
                ))}
              </div>
            </div>

            {/* HOS */}
            <div className="pf-field">
              <div className="pf-hos-state">
                <span>HOS: {formatMin(hos.drive_remaining_min)} / {formatMin(hos.on_duty_remaining_min)} / {formatMin(hos.cycle_remaining_min)}</span>
                <button type="button" onClick={() => setEditHos(!editHos)}>{editHos ? 'Done' : 'Edit'}</button>
              </div>
              {editHos && (
                <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div className="pf-input-row">
                    <div>
                      <span style={{ fontSize: '11px', color: '#475569' }}>Drive (min)</span>
                      <input className="pf-input" type="number" value={hos.drive_remaining_min} onChange={e => setHos({ ...hos, drive_remaining_min: parseInt(e.target.value) || 0 })} />
                    </div>
                    <div>
                      <span style={{ fontSize: '11px', color: '#475569' }}>On-duty (min)</span>
                      <input className="pf-input" type="number" value={hos.on_duty_remaining_min} onChange={e => setHos({ ...hos, on_duty_remaining_min: parseInt(e.target.value) || 0 })} />
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', color: '#475569' }}>Cycle (min)</span>
                    <input className="pf-input" type="number" value={hos.cycle_remaining_min} onChange={e => setHos({ ...hos, cycle_remaining_min: parseInt(e.target.value) || 0 })} style={{ maxWidth: '140px' }} />
                  </div>
                </div>
              )}
            </div>

            {/* Preferences */}
            <div className="pf-field">
              <span className="pf-field-label">Preferences</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <input className="pf-input" type="text" value={preferRegions} onChange={e => setPreferRegions(e.target.value)} placeholder="Prefer: TX, OK, AR" />
                <input className="pf-input" type="text" value={avoidRegions} onChange={e => setAvoidRegions(e.target.value)} placeholder="Avoid: NY, NJ" />
                <input className="pf-input" type="number" value={homeTimeDays} onChange={e => setHomeTimeDays(e.target.value)} placeholder="Home-time target (days)" />
              </div>
            </div>

            {/* Advanced */}
            <details className="pf-advanced">
              <summary>Advanced</summary>
              <div className="pf-advanced-body">
                <div>
                  <span style={{ fontSize: '11px', color: '#475569' }}>Max deadhead (mi)</span>
                  <input className="pf-input" type="number" value={maxDeadhead} onChange={e => setMaxDeadhead(e.target.value)} placeholder="100" />
                </div>
                <div>
                  <span style={{ fontSize: '11px', color: '#475569' }}>Risk tolerance</span>
                  <select className="pf-select" value={riskTolerance} onChange={e => setRiskTolerance(e.target.value as any)}>
                    <option value="low">Low</option>
                    <option value="medium">Balanced</option>
                    <option value="high">Aggressive</option>
                  </select>
                </div>
              </div>
            </details>

            {/* CSV Upload */}
            <CsvUpload onImported={(n) => setCsvCount(prev => prev + n)} />
            {csvCount > 0 && (
              <div style={{ fontSize: '11px', color: '#059669', marginTop: '4px' }}>{csvCount} routes uploaded</div>
            )}
          </div>

          {/* Status bar at bottom of sidebar */}
          <div className="pf-status-bar">
            <button className="pf-update-btn" onClick={handleSubmit} disabled={loading} type="button">
              {loading ? 'Updating...' : lastUpdated ? 'Update Plans' : 'Generate Plans'}
            </button>
            <span className="pf-status-text">
              {lastUpdated
                ? `${planCount || 0} plans · ${loadsAnalyzed || 0} routes · ${lastUpdated}`
                : 'Ready'}
            </span>
          </div>
        </>
      )}
    </div>
  );
};
