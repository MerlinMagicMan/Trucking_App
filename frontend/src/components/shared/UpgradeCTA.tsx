/**
 * UpgradeCTA - Upgrade call-to-action for base tier users (PREVIEW-001)
 *
 * Shows tier-aware messaging. No billing integration - just informational.
 */
import React, { useState } from 'react';

interface UpgradeCTAProps {
  feature: string;
  description?: string;
  compact?: boolean;
}

export const UpgradeCTA: React.FC<UpgradeCTAProps> = ({
  feature,
  description,
  compact = false,
}) => {
  const [showModal, setShowModal] = useState(false);

  if (compact) {
    return (
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          backgroundColor: '#f3e8ff',
          borderRadius: '6px',
          fontSize: '12px',
          color: '#7c3aed',
        }}
      >
        <span style={{ fontWeight: 500 }}>Premium Feature</span>
        <button
          onClick={() => setShowModal(true)}
          style={{
            background: '#7c3aed',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            padding: '2px 8px',
            fontSize: '11px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Learn More
        </button>
        {showModal && <UpgradeModal feature={feature} onClose={() => setShowModal(false)} />}
      </div>
    );
  }

  return (
    <div
      style={{
        padding: '24px',
        backgroundColor: '#faf5ff',
        border: '1px solid #e9d5ff',
        borderRadius: '8px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: '48px',
          height: '48px',
          margin: '0 auto 12px',
          backgroundColor: '#f3e8ff',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '24px',
        }}
      >
        ⬆️
      </div>
      <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 600, color: '#581c87' }}>
        Upgrade to Premium
      </h3>
      <p style={{ margin: '0 0 16px', fontSize: '14px', color: '#7c3aed' }}>
        {description || `${feature} is available on the Premium tier.`}
      </p>
      <button
        onClick={() => setShowModal(true)}
        style={{
          background: '#7c3aed',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          padding: '10px 24px',
          fontSize: '14px',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Learn More
      </button>
      {showModal && <UpgradeModal feature={feature} onClose={() => setShowModal(false)} />}
    </div>
  );
};

interface UpgradeModalProps {
  feature: string;
  onClose: () => void;
}

const UpgradeModal: React.FC<UpgradeModalProps> = ({ feature, onClose }) => {
  return (
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
        <h2 style={{ margin: '0 0 16px', fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
          Premium Features
        </h2>
        <p style={{ margin: '0 0 20px', fontSize: '14px', color: '#475569', lineHeight: 1.6 }}>
          <strong>{feature}</strong> and other advanced features are available on the Premium tier:
        </p>
        <ul style={{ margin: '0 0 24px', paddingLeft: '20px', fontSize: '14px', color: '#334155' }}>
          <li style={{ marginBottom: '8px' }}>Copilot - Plan degradation monitoring</li>
          <li style={{ marginBottom: '8px' }}>Intel - Lane, market, and destination analytics</li>
          <li style={{ marginBottom: '8px' }}>Reports - Prediction calibration insights</li>
          <li style={{ marginBottom: '8px' }}>Confidence-weighted optimization</li>
          <li>Branch plan generation</li>
        </ul>
        <p style={{ margin: '0 0 20px', fontSize: '13px', color: '#64748b' }}>
          Contact your account manager or email support@truckoptimizer.io for upgrade options.
        </p>
        <button
          onClick={onClose}
          style={{
            width: '100%',
            background: '#0f172a',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            padding: '12px',
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
};

export default UpgradeCTA;
