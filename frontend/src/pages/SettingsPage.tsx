/**
 * SettingsPage - Organization settings and tier info (PREVIEW-001)
 * Available to all tiers (read-only)
 */
import React, { useState, useEffect } from 'react';
import { useEntitlement } from '../hooks/useEntitlement';
import type { Tier } from '../hooks/useEntitlement';
import { UpgradeCTA } from '../components/shared/UpgradeCTA';
import { getDataClient } from '../services/dataClient';
import { getActiveOrgId } from '../services/orgContext';
import type { Org } from '../types/org';
import '../styles/preview.css';

type LoadState = 'idle' | 'loading' | 'loaded' | 'offline';

interface HealthInfo {
  status: string;
  version?: string;
}

const TIER_FEATURES: Record<Tier, string[]> = {
  base: ['Preflight (plan generation)', 'Routes management', 'Trucks management', 'Plan history'],
  premium: [
    'All Base features',
    'Copilot (degradation monitoring)',
    'Intel (lane/market analytics)',
    'Reports (calibration)',
    'Confidence-weighted optimization',
    'Branch plan generation',
  ],
  enterprise: [
    'All Premium features',
    'Custom integrations',
    'Dedicated support',
    'SLA guarantees',
  ],
};

export const SettingsPage: React.FC = () => {
  const { tier, isPremium, isLoading: entitlementLoading } = useEntitlement();
  const [org, setOrg] = useState<Org | null>(null);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  useEffect(() => {
    setLoadState('loading');
    const orgId = getActiveOrgId();

    const client = getDataClient();
    Promise.all([
      client.getOrgs().catch(() => []),
      client.checkHealth().catch(() => ({ status: 'offline' })),
    ])
      .then(([orgs, healthData]) => {
        const currentOrg = orgs.find((o) => o.id === orgId) || null;
        setOrg(currentOrg);
        setHealth(healthData);
        setLoadState('loaded');
      })
      .catch(() => {
        setLoadState('offline');
      });
  }, []);

  if (loadState === 'loading' || entitlementLoading) {
    return (
      <div className="page-container">
        <div className="preview-loading">Loading settings...</div>
      </div>
    );
  }

  if (loadState === 'offline') {
    return (
      <div className="page-container">
        <div className="preview-offline">
          Settings unavailable. The backend may be offline.
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: '800px' }}>
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="page-subtitle">Organization configuration and account info</p>
        </div>
      </div>

      {/* Organization Section */}
      <div className="settings-section">
        <h3 className="settings-section-title">Organization</h3>
        <div className="settings-row">
          <span className="settings-label">Name</span>
          <span className="settings-value">{org?.name || 'Unknown'}</span>
        </div>
        <div className="settings-row">
          <span className="settings-label">Organization ID</span>
          <span className="settings-value" style={{ fontFamily: 'monospace', fontSize: '12px' }}>
            {org?.id || 'N/A'}
          </span>
        </div>
        <div className="settings-row">
          <span className="settings-label">Created</span>
          <span className="settings-value">
            {org?.created_at ? new Date(org.created_at).toLocaleDateString() : 'N/A'}
          </span>
        </div>
      </div>

      {/* Tier Section */}
      <div className="settings-section">
        <h3 className="settings-section-title">Subscription Tier</h3>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <span className={`settings-tier-badge ${tier}`}>
            {tier === 'enterprise' ? '⭐' : tier === 'premium' ? '✦' : '○'} {tier}
          </span>
          {!isPremium && (
            <button
              onClick={() => setShowUpgradeModal(true)}
              style={{
                padding: '8px 16px',
                backgroundColor: '#7c3aed',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '13px',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Upgrade
            </button>
          )}
        </div>

        <div style={{ fontSize: '13px', color: '#475569', marginBottom: '16px' }}>
          {tier === 'base' && 'Core plan generation and fleet management features.'}
          {tier === 'premium' && 'Full access to intelligence, copilot, and advanced analytics.'}
          {tier === 'enterprise' && 'Enterprise-grade features with dedicated support.'}
        </div>

        <div className="preview-section-header" style={{ marginTop: '20px' }}>Included Features</div>
        <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#334155' }}>
          {TIER_FEATURES[tier].map((feature, i) => (
            <li key={i} style={{ marginBottom: '6px' }}>{feature}</li>
          ))}
        </ul>
      </div>

      {/* System Info Section */}
      <div className="settings-section">
        <h3 className="settings-section-title">System Information</h3>
        <div className="settings-row">
          <span className="settings-label">API Status</span>
          <span
            className="settings-value"
            style={{
              color: health?.status === 'ok' ? '#059669' : '#dc2626',
              textTransform: 'uppercase',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            {health?.status || 'Unknown'}
          </span>
        </div>
        <div className="settings-row">
          <span className="settings-label">Frontend Version</span>
          <span className="settings-value" style={{ fontFamily: 'monospace' }}>
            1.0.0-preview
          </span>
        </div>
        <div className="settings-row">
          <span className="settings-label">Environment</span>
          <span className="settings-value">
            {window.location.hostname === 'localhost' ? 'Development' : 'Production'}
          </span>
        </div>
      </div>

      {/* Upgrade CTA for base tier */}
      {!isPremium && (
        <div style={{ marginTop: '24px' }}>
          <UpgradeCTA
            feature="Premium Features"
            description="Unlock Copilot, Intel, Reports, and confidence-weighted optimization."
          />
        </div>
      )}

      {/* Upgrade Modal */}
      {showUpgradeModal && (
        <UpgradeModal onClose={() => setShowUpgradeModal(false)} />
      )}
    </div>
  );
};

const UpgradeModal: React.FC<{ onClose: () => void }> = ({ onClose }) => (
  <div
    style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }}
    onClick={onClose}
  >
    <div
      style={{
        backgroundColor: '#fff',
        borderRadius: '12px',
        padding: '32px',
        maxWidth: '400px',
        width: '90%',
        boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <h2 style={{ margin: '0 0 16px', fontSize: '20px', fontWeight: 700 }}>
        Upgrade to Premium
      </h2>
      <p style={{ margin: '0 0 20px', fontSize: '14px', color: '#475569', lineHeight: 1.6 }}>
        Contact your account manager or email <strong>support@truckoptimizer.io</strong> to upgrade your subscription.
      </p>
      <button
        onClick={onClose}
        style={{
          width: '100%',
          padding: '12px',
          backgroundColor: '#0f172a',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          fontSize: '14px',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Got it
      </button>
    </div>
  </div>
);

export default SettingsPage;
