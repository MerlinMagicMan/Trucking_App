import React, { useEffect, useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import type { Org, Truck } from '../../types/org';
import { getDataClient, isDemoActive } from '../../services/dataClient';
import { getActiveOrgId, setActiveOrgId, getActiveTruckId, setActiveTruckId } from '../../services/orgContext';
import '../../styles/shell.css';

const NAV_ITEMS = [
  { section: 'Planning' },
  { path: '/plans', label: 'Preflight', icon: '◈' },
  { path: '/copilot', label: 'Copilot', icon: '◉', badge: 'Preview' },
  { path: '/intel', label: 'Intel', icon: '◎', badge: 'Preview' },
  { section: 'Data' },
  { path: '/routes', label: 'Routes', icon: '⇄' },
  { path: '/assets/trucks', label: 'Trucks', icon: '▣' },
  { path: '/maintenance', label: 'Maintenance', icon: '⚙', badge: 'Preview' },
  { section: 'Analytics' },
  { path: '/plans/history', label: 'Plans History', icon: '▤' },
  { path: '/reports', label: 'Reports', icon: '▥', badge: 'Preview' },
  { section: '' },
  { path: '/settings', label: 'Settings', icon: '⚙' },
  { path: '/admin', label: 'Admin', icon: '⚙' },
];

export const AppShell: React.FC = () => {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [trucks, setTrucks] = useState<Truck[]>([]);
  const [activeOrgId, setActiveOrgState] = useState<string>(getActiveOrgId() || '');
  const [activeTruckId, setActiveTruckState] = useState<string>(getActiveTruckId() || '');
  const [dataStatus, setDataStatus] = useState<{ label: string; color: string }>({ label: 'Offline', color: '#94a3b8' });

  // Load orgs on mount
  useEffect(() => {
    getDataClient()
      .getOrgs()
      .then((data) => {
        setOrgs(data);
        // Default to first org if none selected
        if (!getActiveOrgId() && data.length > 0) {
          setActiveOrgId(data[0].id);
          setActiveOrgState(data[0].id);
        }
      })
      .catch(() => {
        // Backend unavailable — use placeholder
        setOrgs([]);
      });
  }, []);

  // Load trucks when org changes
  useEffect(() => {
    if (!activeOrgId) return;
    getDataClient()
      .getTrucks()
      .then((data) => {
        setTrucks(data);
        const currentTruck = getActiveTruckId();
        if (!currentTruck && data.length > 0) {
          setActiveTruckId(data[0].id);
          setActiveTruckState(data[0].id);
        }
      })
      .catch(() => setTrucks([]));
  }, [activeOrgId]);

  // Poll ingestion status
  useEffect(() => {
    if (!activeOrgId) return;
    const check = () => {
      getDataClient()
        .getIngestionStatus()
        .then((s) => {
          if (isDemoActive()) {
            setDataStatus({ label: 'Demo', color: '#3b82f6' });
          } else if (s.scheduler.running && s.snapshots.active > 0) {
            setDataStatus({ label: `Live (${s.snapshots.active})`, color: '#22c55e' });
          } else if (s.scheduler.running) {
            setDataStatus({ label: 'Simulated', color: '#eab308' });
          } else {
            setDataStatus({ label: 'Offline', color: '#94a3b8' });
          }
        })
        .catch(() => {
          if (isDemoActive()) {
            setDataStatus({ label: 'Demo', color: '#3b82f6' });
          } else {
            setDataStatus({ label: 'Offline', color: '#94a3b8' });
          }
        });
    };
    check();
    const interval = setInterval(check, 60_000);
    return () => clearInterval(interval);
  }, [activeOrgId]);

  const handleOrgChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setActiveOrgId(id);
    setActiveOrgState(id);
    // Reset truck selection on org change
    setActiveTruckId('');
    setActiveTruckState('');
  };

  const handleTruckChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setActiveTruckId(id);
    setActiveTruckState(id);
  };

  const activeOrgName = orgs.find((o) => o.id === activeOrgId)?.name || 'No Org';
  const activeTruckName = trucks.find((t) => t.id === activeTruckId)?.name || 'No Truck';

  return (
    <div className="shell">
      {/* Sidebar */}
      <aside className="shell-sidebar">
        <div className="shell-logo">
          Truck Optimizer
          <span>Enterprise Platform</span>
        </div>
        <nav className="shell-nav">
          {NAV_ITEMS.map((item, i) => {
            if ('section' in item && !('path' in item)) {
              return item.section ? (
                <div key={i} className="shell-nav-section">
                  <div className="shell-nav-section-label">{item.section}</div>
                </div>
              ) : (
                <div key={i} style={{ height: '8px' }} />
              );
            }
            const navItem = item as { path: string; label: string; icon: string; disabled?: boolean; badge?: string };
            if (navItem.disabled) {
              return (
                <div key={i} className="shell-nav-section">
                  <div className="shell-nav-item disabled">
                    <span className="nav-icon">{navItem.icon}</span>
                    {navItem.label}
                    {navItem.badge && <span className="nav-badge">{navItem.badge}</span>}
                  </div>
                </div>
              );
            }
            return (
              <div key={i} className="shell-nav-section">
                <NavLink
                  to={navItem.path}
                  className={({ isActive }) => `shell-nav-item ${isActive ? 'active' : ''}`}
                >
                  <span className="nav-icon">{navItem.icon}</span>
                  {navItem.label}
                  {navItem.badge && <span className="nav-badge">{navItem.badge}</span>}
                </NavLink>
              </div>
            );
          })}
        </nav>
      </aside>

      {/* Top Bar */}
      <header className="shell-topbar">
        <div className="shell-topbar-left">
          <div className="shell-selector">
            <span className="shell-selector-label">Organization</span>
            <select value={activeOrgId} onChange={handleOrgChange}>
              {orgs.length === 0 && <option value="">Loading...</option>}
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
          </div>
          <div className="shell-selector">
            <span className="shell-selector-label">Active Truck</span>
            <select value={activeTruckId} onChange={handleTruckChange}>
              {trucks.length === 0 && <option value="">No trucks</option>}
              {trucks.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="shell-topbar-right">
          <span
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: dataStatus.color,
              border: `1px solid ${dataStatus.color}`,
              borderRadius: '4px',
              padding: '2px 8px',
            }}
            title="Data pipeline status"
          >
            {dataStatus.label}
          </span>
          <span style={{ fontSize: '12px', color: '#94a3b8' }}>
            {activeOrgName} · {activeTruckName}
          </span>
          <button className="shell-notification-btn" title="Notifications" type="button">
            🔔
          </button>
        </div>
      </header>

      {/* Canvas */}
      <main className="shell-canvas">
        <Outlet />
      </main>
    </div>
  );
};
