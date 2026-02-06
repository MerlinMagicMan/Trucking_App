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

export const AdminPage: React.FC = () => {
  const [demoEnabled, setDemoEnabled] = useState(getDemoMode());
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl() || '');
  const [adminOverride, setAdminOverrideState] = useState(getAdminOverride());
  const [demoActive, setDemoActiveState] = useState(isDemoActive());
  const [seedStatus, setSeedStatus] = useState<string | null>(null);
  const [stats, setStats] = useState<{ orgs: number; trucks: number; routes: number; history: number } | null>(null);

  // Load stats on mount
  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const client = getDataClient();
      const [orgs, trucks, routes, history] = await Promise.all([
        client.getOrgs().catch(() => []),
        client.getTrucks().catch(() => []),
        client.getRoutes().catch(() => []),
        client.getPlanHistory().catch(() => []),
      ]);
      setStats({
        orgs: orgs.length,
        trucks: trucks.length,
        routes: routes.length,
        history: history.length,
      });
    } catch {
      setStats(null);
    }
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
    setApiBaseUrl(apiUrl);
    setDemoActiveState(isDemoActive());
    setSeedStatus('API URL saved');
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

  return (
    <div className="page-container" style={{ maxWidth: '900px' }}>
      <div className="page-header">
        <div>
          <h1>Admin Console</h1>
          <p className="page-subtitle">Demo mode controls and system administration</p>
        </div>
      </div>

      {/* Status Banner */}
      <div
        style={{
          padding: '16px 20px',
          borderRadius: '8px',
          marginBottom: '24px',
          backgroundColor: demoActive ? '#eff6ff' : '#f0fdf4',
          border: `1px solid ${demoActive ? '#bfdbfe' : '#bbf7d0'}`,
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <span
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: demoActive ? '#3b82f6' : '#22c55e',
          }}
        />
        <span style={{ fontSize: '14px', fontWeight: 500, color: demoActive ? '#1e40af' : '#166534' }}>
          {demoActive ? 'Demo Mode Active' : 'Live Mode Active'}
        </span>
        {adminOverride && (
          <span
            style={{
              marginLeft: 'auto',
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

      {/* Data Stats */}
      {stats && (
        <div className="preview-metrics" style={{ marginBottom: '24px' }}>
          <div className="preview-metric-card" style={{ background: '#fff' }}>
            <div className="preview-metric-label">Organizations</div>
            <div className="preview-metric-value">{stats.orgs}</div>
          </div>
          <div className="preview-metric-card" style={{ background: '#fff' }}>
            <div className="preview-metric-label">Trucks</div>
            <div className="preview-metric-value">{stats.trucks}</div>
          </div>
          <div className="preview-metric-card" style={{ background: '#fff' }}>
            <div className="preview-metric-label">Routes</div>
            <div className="preview-metric-value">{stats.routes}</div>
          </div>
          <div className="preview-metric-card" style={{ background: '#fff' }}>
            <div className="preview-metric-label">Plan History</div>
            <div className="preview-metric-value">{stats.history}</div>
          </div>
        </div>
      )}

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
