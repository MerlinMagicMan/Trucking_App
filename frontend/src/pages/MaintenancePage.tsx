/**
 * MaintenancePage - System maintenance stub (PREVIEW-001)
 * Functional stub showing system health and basic stats
 */
import React, { useState, useEffect } from 'react';
import { PreviewBadge } from '../components/shared/PreviewBadge';
import { fetchTrucks, fetchRoutes, checkHealth, fetchIngestionStatus } from '../services/api';
import type { IngestionStatus } from '../services/api';
import '../styles/preview.css';

type LoadState = 'idle' | 'loading' | 'loaded' | 'offline';

interface SystemStats {
  trucksCount: number;
  routesCount: number;
  health: { status: string };
  ingestion: IngestionStatus | null;
}

export const MaintenancePage: React.FC = () => {
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    setLoadState('loading');

    Promise.all([
      fetchTrucks().catch(() => []),
      fetchRoutes().catch(() => []),
      checkHealth().catch(() => ({ status: 'offline' })),
      fetchIngestionStatus().catch(() => null),
    ])
      .then(([trucks, routes, health, ingestion]) => {
        setStats({
          trucksCount: trucks.length,
          routesCount: routes.length,
          health,
          ingestion,
        });
        setLoadState('loaded');
      })
      .catch(() => {
        setLoadState('offline');
      });
  }, []);

  return (
    <div className="page-container" style={{ maxWidth: '900px' }}>
      <div className="preview-page-header">
        <div>
          <h1>Maintenance</h1>
          <p className="preview-page-subtitle">System health and maintenance tools</p>
        </div>
        <PreviewBadge variant="coming-soon" />
      </div>

      {/* Under Construction Banner */}
      <div className="stub-container" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px', marginBottom: '24px' }}>
        <div className="stub-icon">🚧</div>
        <h2 className="stub-title">Under Construction</h2>
        <p className="stub-description">
          Full maintenance features are coming soon. For now, here's a quick view of your system status.
        </p>
      </div>

      {loadState === 'loading' ? (
        <div className="preview-loading">Loading system status...</div>
      ) : loadState === 'offline' ? (
        <div className="preview-offline">
          Unable to fetch system status. The backend may be offline.
        </div>
      ) : stats ? (
        <>
          {/* Quick Stats */}
          <div className="preview-metrics" style={{ marginBottom: '24px' }}>
            <div className="preview-metric-card" style={{ background: '#fff' }}>
              <div className="preview-metric-label">Trucks</div>
              <div className="preview-metric-value">{stats.trucksCount}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff' }}>
              <div className="preview-metric-label">Routes</div>
              <div className="preview-metric-value">{stats.routesCount}</div>
            </div>
            <div className="preview-metric-card" style={{ background: '#fff' }}>
              <div className="preview-metric-label">API Status</div>
              <div className={`preview-metric-value ${stats.health.status === 'ok' ? 'green' : 'red'}`} style={{ fontSize: '20px', textTransform: 'uppercase' }}>
                {stats.health.status}
              </div>
            </div>
          </div>

          {/* Ingestion Status */}
          {stats.ingestion && (
            <div className="card" style={{ marginBottom: '24px' }}>
              <h3 style={{ margin: '0 0 16px', fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>
                Data Ingestion
              </h3>
              <ul className="preview-list">
                <li className="preview-list-item">
                  <span className="preview-list-label">Scheduler</span>
                  <span
                    className="preview-list-value"
                    style={{ color: stats.ingestion.scheduler.running ? '#059669' : '#94a3b8' }}
                  >
                    {stats.ingestion.scheduler.running ? 'Running' : 'Stopped'}
                  </span>
                </li>
                <li className="preview-list-item">
                  <span className="preview-list-label">Interval</span>
                  <span className="preview-list-value">
                    {stats.ingestion.scheduler.interval_minutes} min
                  </span>
                </li>
                <li className="preview-list-item">
                  <span className="preview-list-label">Active Snapshots</span>
                  <span className="preview-list-value">{stats.ingestion.snapshots.active}</span>
                </li>
                <li className="preview-list-item">
                  <span className="preview-list-label">Expired Snapshots</span>
                  <span className="preview-list-value">{stats.ingestion.snapshots.expired}</span>
                </li>
                <li className="preview-list-item">
                  <span className="preview-list-label">Total Snapshots</span>
                  <span className="preview-list-value">{stats.ingestion.snapshots.total}</span>
                </li>
              </ul>
            </div>
          )}

          {/* Planned Features */}
          <div className="card">
            <h3 style={{ margin: '0 0 16px', fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>
              Planned Features
            </h3>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#64748b' }}>
              <li style={{ marginBottom: '8px' }}>Database maintenance tools</li>
              <li style={{ marginBottom: '8px' }}>Cache management</li>
              <li style={{ marginBottom: '8px' }}>Log viewer and export</li>
              <li style={{ marginBottom: '8px' }}>Scheduled task management</li>
              <li style={{ marginBottom: '8px' }}>System diagnostics</li>
              <li>Backup and restore</li>
            </ul>
          </div>
        </>
      ) : null}
    </div>
  );
};

export default MaintenancePage;
