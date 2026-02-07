/**
 * AdminPage - Demo mode administration (DEMO-001)
 * Provides seed data controls, reset functionality, and admin override
 */
import React, { useState, useEffect } from 'react';
import {
  getDemoMode,
  setDemoMode,
  getApiBaseUrl,
  setApiBaseUrl,
  getAdminOverride,
  setAdminOverride,
  isDemoActive,
} from '../services/demoConfig';
import {
  seedAllDemoData,
  resetDemoData,
  SAMPLE_CSV_DATA,
} from '../services/seedData';
import { getDataClient } from '../services/dataClient';
import '../styles/preview.css';

// Demo localStorage keys for integrity checking
const DEMO_KEYS = {
  config: 'demo_v1_config',
  orgs: 'demo_v1_orgs',
  trucks: 'demo_v1_trucks',
  routes: 'demo_v1_routes',
  planHistory: 'demo_v1_plan_history',
  outcomes: 'demo_v1_outcomes',
  predictionSnapshots: 'demo_v1_prediction_snapshots',
  decisions: 'demo_v1_decisions',
  activeSnapshot: 'demo_v1_active_snapshot',
};

interface DataStats {
  orgs: number;
  trucks: number;
  routes: number;
  history: number;
  outcomes: number;
  decisions: number;
  snapshots: number;
  activeSnapshot: boolean;
}

interface IntegrityStatus {
  healthy: boolean;
  issues: string[];
}

type ApiHealth = 'checking' | 'healthy' | 'unreachable' | 'error';

export const AdminPage: React.FC = () => {
  const [demoEnabled, setDemoEnabled] = useState(getDemoMode());
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl() || '');
  const [adminOverride, setAdminOverrideState] = useState(getAdminOverride());
  const [demoActive, setDemoActiveState] = useState(isDemoActive());
  const [seedStatus, setSeedStatus] = useState<string | null>(null);
  const [stats, setStats] = useState<DataStats | null>(null);
  const [apiHealth, setApiHealth] = useState<ApiHealth>('checking');
  const [apiLastChecked, setApiLastChecked] = useState<string | null>(null);
  const [integrity, setIntegrity] = useState<IntegrityStatus>({ healthy: true, issues: [] });

  // Load stats and health on mount
  useEffect(() => {
    loadStats();
    checkApiHealth();
    checkIntegrity();
  }, []);

  const loadStats = async () => {
    try {
      const client = getDataClient();
      const [orgs, trucks, routes, history, outcomeSummary] = await Promise.all([
        client.getOrgs().catch(() => []),
        client.getTrucks().catch(() => []),
        client.getRoutes().catch(() => []),
        client.getPlanHistory().catch(() => []),
        client.getOutcomeSummary().catch(() => []),
      ]);

      // Count snapshots from localStorage for demo mode
      const snapshotsRaw = localStorage.getItem(DEMO_KEYS.predictionSnapshots);
      const snapshots = snapshotsRaw ? JSON.parse(snapshotsRaw) : [];

      // Count decisions from localStorage for demo mode
      const decisionsRaw = localStorage.getItem(DEMO_KEYS.decisions);
      const decisionsArr = decisionsRaw ? JSON.parse(decisionsRaw) : [];

      // Check active snapshot
      const activeSnapshot = localStorage.getItem(DEMO_KEYS.activeSnapshot) !== null;

      setStats({
        orgs: orgs.length,
        trucks: trucks.length,
        routes: routes.length,
        history: history.length,
        outcomes: outcomeSummary.length,
        decisions: decisionsArr.length,
        snapshots: snapshots.length,
        activeSnapshot,
      });
    } catch {
      setStats(null);
    }
  };

  const checkApiHealth = async () => {
    setApiHealth('checking');
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) {
      setApiHealth('unreachable');
      setApiLastChecked(new Date().toLocaleTimeString());
      return;
    }
    try {
      const response = await fetch(`${baseUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      setApiLastChecked(new Date().toLocaleTimeString());
      if (response.ok) {
        setApiHealth('healthy');
      } else {
        setApiHealth('error');
      }
    } catch {
      setApiHealth('unreachable');
      setApiLastChecked(new Date().toLocaleTimeString());
    }
  };

  const checkIntegrity = () => {
    const issues: string[] = [];

    // Check each localStorage key for valid JSON
    Object.entries(DEMO_KEYS).forEach(([name, key]) => {
      const data = localStorage.getItem(key);
      if (data) {
        try {
          JSON.parse(data);
        } catch {
          issues.push(`Corrupted data in ${name} (${key})`);
        }
      }
    });

    // Check for orphaned plan_detail keys
    const historyRaw = localStorage.getItem(DEMO_KEYS.planHistory);
    const history = historyRaw ? JSON.parse(historyRaw) : [];
    const historyIds = new Set(history.map((h: { id: number }) => h.id));

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith('demo_v1_plan_detail_')) {
        const id = parseInt(key.replace('demo_v1_plan_detail_', ''), 10);
        if (!historyIds.has(id)) {
          issues.push(`Orphaned plan detail: ${key}`);
        }
      }
    }

    // Check for required references
    const orgsRaw = localStorage.getItem(DEMO_KEYS.orgs);
    const trucksRaw = localStorage.getItem(DEMO_KEYS.trucks);
    if (trucksRaw && orgsRaw) {
      const orgs = JSON.parse(orgsRaw);
      const trucks = JSON.parse(trucksRaw);
      const orgIds = new Set(orgs.map((o: { id: string }) => o.id));
      trucks.forEach((t: { org_id: string; name: string }) => {
        if (!orgIds.has(t.org_id)) {
          issues.push(`Truck "${t.name}" references missing org`);
        }
      });
    }

    setIntegrity({ healthy: issues.length === 0, issues });
  };

  const handleDemoToggle = () => {
    const newValue = !demoEnabled;
    setDemoMode(newValue);
    setDemoEnabled(newValue);
    setDemoActiveState(isDemoActive());
    setSeedStatus(newValue ? 'Demo mode enabled' : 'Demo mode disabled');
    setTimeout(() => {
      window.location.reload();
    }, 500);
  };

  const handleApiUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const url = e.target.value;
    setApiUrl(url);
  };

  const handleApiUrlSave = () => {
    const trimmedUrl = apiUrl.trim();
    setApiUrl(trimmedUrl);
    setApiBaseUrl(trimmedUrl);
    setDemoActiveState(isDemoActive());
    setSeedStatus('API URL saved');
    // Test connection after saving
    setTimeout(() => checkApiHealth(), 100);
  };

  const handleAdminOverrideToggle = () => {
    const newValue = !adminOverride;
    setAdminOverride(newValue);
    setAdminOverrideState(newValue);
    setSeedStatus(newValue ? 'Admin override enabled - you now have enterprise access' : 'Admin override disabled');
    setTimeout(() => {
      window.location.reload();
    }, 500);
  };

  const handleSeedData = () => {
    seedAllDemoData();
    setSeedStatus('Demo data seeded successfully');
    loadStats();
  };

  const handleResetData = () => {
    if (window.confirm('This will delete all demo data. Are you sure?')) {
      resetDemoData();
      setSeedStatus('Demo data reset');
      loadStats();
    }
  };

  const handleDownloadCsv = () => {
    const csvContent = SAMPLE_CSV_DATA;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sample_routes.csv';
    link.click();
    URL.revokeObjectURL(url);
    setSeedStatus('Sample CSV downloaded');
  };

  const handleOneClickSetup = () => {
    // Enable demo mode
    setDemoMode(true);
    setDemoEnabled(true);

    // Enable admin override
    setAdminOverride(true);
    setAdminOverrideState(true);

    // Seed all demo data
    seedAllDemoData();

    // Update state
    setDemoActiveState(true);
    setSeedStatus('Full access enabled + demo data seeded! Reloading...');
    loadStats();
    checkIntegrity();

    // Reload to apply changes
    setTimeout(() => {
      window.location.reload();
    }, 1000);
  };

  const handleRepairIntegrity = () => {
    // Remove orphaned plan_detail keys
    const historyRaw = localStorage.getItem(DEMO_KEYS.planHistory);
    const history = historyRaw ? JSON.parse(historyRaw) : [];
    const historyIds = new Set(history.map((h: { id: number }) => h.id));

    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith('demo_v1_plan_detail_')) {
        const id = parseInt(key.replace('demo_v1_plan_detail_', ''), 10);
        if (!historyIds.has(id)) {
          keysToRemove.push(key);
        }
      }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key));

    // Re-check integrity
    checkIntegrity();
    loadStats();
    setSeedStatus(`Repaired ${keysToRemove.length} orphaned entries`);
  };

  return (
    <div className="page-container" style={{ maxWidth: '900px' }}>
      <div className="page-header">
        <div>
          <h1>Admin Console</h1>
          <p className="page-subtitle">Demo mode controls and system administration</p>
        </div>
      </div>

      {/* Health Check Section (C1) */}
      <div
        style={{
          padding: '16px 20px',
          borderRadius: '8px',
          marginBottom: '24px',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          {/* Mode Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: demoActive ? '#3b82f6' : '#22c55e',
              }}
            />
            <span style={{ fontSize: '14px', fontWeight: 500, color: demoActive ? '#1e40af' : '#166534' }}>
              {demoActive ? 'Demo Mode' : 'Live Mode'}
            </span>
          </div>

          {/* API Health */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor:
                  apiHealth === 'healthy'
                    ? '#22c55e'
                    : apiHealth === 'checking'
                      ? '#eab308'
                      : '#ef4444',
              }}
            />
            <span
              style={{
                fontSize: '14px',
                fontWeight: 500,
                color:
                  apiHealth === 'healthy'
                    ? '#166534'
                    : apiHealth === 'checking'
                      ? '#854d0e'
                      : '#991b1b',
              }}
            >
              API:{' '}
              {apiHealth === 'checking'
                ? 'Checking...'
                : apiHealth === 'healthy'
                  ? 'Healthy'
                  : apiHealth === 'unreachable'
                    ? 'Unreachable'
                    : 'Error'}
            </span>
            {apiLastChecked && (
              <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                @{apiLastChecked}
              </span>
            )}
            <button
              onClick={checkApiHealth}
              style={{
                padding: '2px 8px',
                fontSize: '11px',
                backgroundColor: '#e2e8f0',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Retry
            </button>
          </div>

          {/* Data Integrity */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: integrity.healthy ? '#22c55e' : '#ef4444',
              }}
            />
            <span
              style={{
                fontSize: '14px',
                fontWeight: 500,
                color: integrity.healthy ? '#166534' : '#991b1b',
              }}
            >
              Data: {integrity.healthy ? 'OK' : `${integrity.issues.length} issues`}
            </span>
          </div>

          {/* Badges */}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
            {adminOverride && (
              <span
                style={{
                  padding: '4px 10px',
                  backgroundColor: '#fef3c7',
                  color: '#92400e',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                }}
              >
                Admin Override
              </span>
            )}
          </div>
        </div>
      </div>

      {seedStatus && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '6px',
            marginBottom: '16px',
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#166534',
            fontSize: '13px',
          }}
        >
          {seedStatus}
        </div>
      )}

      {/* Data Integrity Section (C2) */}
      {stats && (
        <div className="settings-section" style={{ marginBottom: '24px' }}>
          <h3 className="settings-section-title">Data Inventory</h3>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '12px',
              marginBottom: '16px',
            }}
          >
            <div className="preview-metric-card" style={{ background: '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Organizations</div>
              <div className="preview-metric-value">{stats.orgs}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Trucks</div>
              <div className="preview-metric-value">{stats.trucks}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Routes</div>
              <div className="preview-metric-value">{stats.routes}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Plan History</div>
              <div className="preview-metric-value">{stats.history}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Outcomes</div>
              <div className="preview-metric-value">{stats.outcomes}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Decisions</div>
              <div className="preview-metric-value">{stats.decisions}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Snapshots</div>
              <div className="preview-metric-value">{stats.snapshots}</div>
            </div>
            <div className="preview-metric-card" style={{ background: stats.activeSnapshot ? '#f0fdf4' : '#fff', padding: '12px' }}>
              <div className="preview-metric-label">Active Snapshot</div>
              <div className="preview-metric-value">{stats.activeSnapshot ? 'Yes' : 'No'}</div>
            </div>
          </div>

          {/* Integrity Issues */}
          {!integrity.healthy && (
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '6px',
                marginBottom: '12px',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '13px', color: '#991b1b', marginBottom: '8px' }}>
                Data Integrity Issues Detected
              </div>
              <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: '#dc2626' }}>
                {integrity.issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
              <button
                onClick={handleRepairIntegrity}
                style={{
                  marginTop: '12px',
                  padding: '6px 12px',
                  backgroundColor: '#dc2626',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                Repair Issues
              </button>
            </div>
          )}
        </div>
      )}

      {/* One-Click Setup (C3) */}
      <div className="settings-section" style={{ backgroundColor: '#fefce8', border: '1px solid #fef08a', borderRadius: '8px', padding: '20px' }}>
        <h3 className="settings-section-title" style={{ marginTop: 0 }}>Quick Setup</h3>
        <p style={{ fontSize: '13px', color: '#713f12', marginBottom: '16px' }}>
          New to the app? One click enables demo mode, admin access, and seeds sample data.
        </p>
        <button
          onClick={handleOneClickSetup}
          style={{
            padding: '12px 24px',
            backgroundColor: '#f59e0b',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span style={{ fontSize: '18px' }}>&#9889;</span>
          Enable Full Access + Seed Everything
        </button>
      </div>

      {/* Demo Mode Toggle */}
      <div className="settings-section">
        <h3 className="settings-section-title">Demo Mode</h3>
        <div className="settings-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span className="settings-label">Enable Demo Mode</span>
            <p style={{ fontSize: '12px', color: '#64748b', margin: '4px 0 0' }}>
              Use localStorage for all data. No backend required.
            </p>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={demoEnabled}
              onChange={handleDemoToggle}
              style={{ width: '18px', height: '18px', accentColor: '#3b82f6' }}
            />
          </label>
        </div>
      </div>

      {/* Admin Override */}
      <div className="settings-section">
        <h3 className="settings-section-title">Admin Override</h3>
        <div className="settings-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span className="settings-label">Enable Full Access</span>
            <p style={{ fontSize: '12px', color: '#64748b', margin: '4px 0 0' }}>
              Grants enterprise tier access to all features (bypasses tier checks).
            </p>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={adminOverride}
              onChange={handleAdminOverrideToggle}
              style={{ width: '18px', height: '18px', accentColor: '#f59e0b' }}
            />
          </label>
        </div>
      </div>

      {/* API Configuration */}
      <div className="settings-section">
        <h3 className="settings-section-title">API Configuration</h3>
        <div className="settings-row">
          <span className="settings-label">API Base URL</span>
          <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
            <input
              type="text"
              value={apiUrl}
              onChange={handleApiUrlChange}
              placeholder="http://localhost:8000"
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid #e2e8f0',
                fontSize: '13px',
              }}
            />
            <button
              onClick={handleApiUrlSave}
              style={{
                padding: '8px 16px',
                backgroundColor: '#0f172a',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Save
            </button>
          </div>
          <p style={{ fontSize: '12px', color: '#64748b', margin: '8px 0 0' }}>
            Leave empty or set invalid URL to auto-enable demo mode.
          </p>
        </div>
      </div>

      {/* Seed Data Actions */}
      <div className="settings-section">
        <h3 className="settings-section-title">Demo Data</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
          <button
            onClick={handleSeedData}
            style={{
              padding: '10px 20px',
              backgroundColor: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Seed Demo Data
          </button>
          <button
            onClick={handleResetData}
            style={{
              padding: '10px 20px',
              backgroundColor: '#dc2626',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Reset All Data
          </button>
          <button
            onClick={handleDownloadCsv}
            style={{
              padding: '10px 20px',
              backgroundColor: '#059669',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Download Sample CSV
          </button>
          <button
            onClick={loadStats}
            style={{
              padding: '10px 20px',
              backgroundColor: '#64748b',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Refresh Stats
          </button>
        </div>
        <p style={{ fontSize: '12px', color: '#64748b', margin: '12px 0 0' }}>
          Seeding creates 1 org, 1 truck, and 20 sample routes. Reset clears all localStorage demo data.
        </p>
      </div>

      {/* Sample CSV Preview */}
      <div className="settings-section">
        <h3 className="settings-section-title">Sample CSV Format</h3>
        <pre
          style={{
            backgroundColor: '#f8fafc',
            padding: '12px',
            borderRadius: '6px',
            fontSize: '11px',
            overflow: 'auto',
            maxHeight: '200px',
            border: '1px solid #e2e8f0',
          }}
        >
          {SAMPLE_CSV_DATA.split('\n').slice(0, 6).join('\n')}
          {'\n...'}
        </pre>
      </div>

      {/* Quick Start Guide */}
      <div className="settings-section">
        <h3 className="settings-section-title">Quick Start</h3>
        <ol style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#475569', lineHeight: 1.8 }}>
          <li>Enable <strong>Demo Mode</strong> above (or leave API URL empty)</li>
          <li>Click <strong>Seed Demo Data</strong> to populate sample org, truck, and routes</li>
          <li>Enable <strong>Admin Override</strong> to access premium features</li>
          <li>Navigate to <strong>Preflight</strong> to generate plans</li>
          <li>Explore <strong>Copilot</strong>, <strong>Intel</strong>, and <strong>Reports</strong> pages</li>
        </ol>
      </div>
    </div>
  );
};

export default AdminPage;
