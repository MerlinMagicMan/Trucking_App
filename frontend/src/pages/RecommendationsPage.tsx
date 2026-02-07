/**
 * Recommendations Page (Wave 2: Snapshot Flow)
 *
 * Displays recommendations from the active snapshot.
 * Grouped by category: Operational, Negotiation, Risk.
 * Works fully offline with localStorage persistence.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getActiveSnapshot,
  type SnapshotRecommendation,
} from '../services/snapshotStorage';

const CATEGORY_CONFIG: Record<
  SnapshotRecommendation['category'],
  { label: string; color: string; bg: string; icon: string }
> = {
  operational: { label: 'Operational', color: '#1d4ed8', bg: '#eff6ff', icon: '⚙' },
  negotiation: { label: 'Negotiation', color: '#0d9488', bg: '#f0fdfa', icon: '$' },
  risk: { label: 'Risk', color: '#dc2626', bg: '#fef2f2', icon: '⚠' },
};

const IMPACT_CONFIG: Record<string, { color: string; bg: string }> = {
  high: { color: '#991b1b', bg: '#fee2e2' },
  medium: { color: '#92400e', bg: '#fef3c7' },
  low: { color: '#166534', bg: '#dcfce7' },
};

export default function RecommendationsPage() {
  const navigate = useNavigate();
  const snapshot = getActiveSnapshot();

  if (!snapshot) {
    return (
      <div className="page-container" style={{ maxWidth: '900px' }}>
        <div className="page-header">
          <h1>Recommendations</h1>
        </div>
        <div
          style={{
            padding: '40px',
            textAlign: 'center',
            backgroundColor: '#fef2f2',
            borderRadius: '8px',
            border: '1px solid #fecaca',
          }}
        >
          <h3 style={{ margin: '0 0 8px', fontSize: '18px', color: '#991b1b' }}>
            No Active Snapshot
          </h3>
          <p style={{ margin: '0 0 16px', color: '#64748b', fontSize: '14px' }}>
            Generate a snapshot first to see recommendations.
          </p>
          <button
            onClick={() => navigate('/snapshot')}
            style={{
              padding: '10px 20px',
              backgroundColor: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Go to Snapshot
          </button>
        </div>
      </div>
    );
  }

  // Group recommendations by category
  const grouped = {
    operational: snapshot.recommendations.filter((r) => r.category === 'operational'),
    negotiation: snapshot.recommendations.filter((r) => r.category === 'negotiation'),
    risk: snapshot.recommendations.filter((r) => r.category === 'risk'),
  };

  return (
    <div className="page-container" style={{ maxWidth: '1100px' }}>
      <div className="page-header">
        <div>
          <h1>Recommendations</h1>
          <p className="page-subtitle">
            Based on your selected plan with ${snapshot.plan_summary.profit_per_day.toFixed(0)}/day
            earnings potential
          </p>
        </div>
      </div>

      {/* Plan Summary Card */}
      <div
        style={{
          display: 'flex',
          gap: '16px',
          marginBottom: '24px',
          padding: '16px 20px',
          backgroundColor: '#f8fafc',
          borderRadius: '8px',
          border: '1px solid #e2e8f0',
          flexWrap: 'wrap',
        }}
      >
        <SummaryMetric
          label="Net Profit"
          value={`$${snapshot.plan_summary.net_profit.toFixed(0)}`}
          highlight
        />
        <SummaryMetric
          label="Profit/Day"
          value={`$${snapshot.plan_summary.profit_per_day.toFixed(0)}`}
        />
        <SummaryMetric label="Loads" value={String(snapshot.plan_summary.num_loads)} />
        <SummaryMetric label="Ends At" value={snapshot.plan_summary.end_location} />
        {snapshot.trust_score !== null && snapshot.trust_score !== undefined && (
          <SummaryMetric
            label="Trust Score"
            value={`${snapshot.trust_score}/100`}
            color={
              snapshot.trust_score >= 80
                ? '#16a34a'
                : snapshot.trust_score >= 55
                  ? '#d97706'
                  : '#dc2626'
            }
          />
        )}
      </div>

      {/* Recommendations by Category */}
      <div style={{ display: 'grid', gap: '24px' }}>
        {(['operational', 'negotiation', 'risk'] as const).map((category) => {
          const recs = grouped[category];
          const config = CATEGORY_CONFIG[category];
          if (recs.length === 0) return null;

          return (
            <div key={category}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '12px',
                }}
              >
                <span
                  style={{
                    width: '28px',
                    height: '28px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: config.bg,
                    color: config.color,
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                >
                  {config.icon}
                </span>
                <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#0f172a' }}>
                  {config.label}
                </h2>
                <span
                  style={{
                    fontSize: '12px',
                    color: '#64748b',
                    marginLeft: '4px',
                  }}
                >
                  ({recs.length})
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {recs.map((rec) => (
                  <RecommendationCard key={rec.id} rec={rec} categoryConfig={config} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Navigation */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          marginTop: '32px',
          paddingTop: '24px',
          borderTop: '1px solid #e2e8f0',
        }}
      >
        <button
          onClick={() => navigate('/forward-look')}
          style={{
            padding: '12px 24px',
            backgroundColor: '#3b82f6',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          View Forward Look
        </button>
        <button
          onClick={() => navigate('/snapshot')}
          style={{
            padding: '12px 24px',
            backgroundColor: '#f1f5f9',
            color: '#475569',
            border: 'none',
            borderRadius: '6px',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          ← Back to Snapshot
        </button>
      </div>
    </div>
  );
}

interface SummaryMetricProps {
  label: string;
  value: string;
  highlight?: boolean;
  color?: string;
}

const SummaryMetric: React.FC<SummaryMetricProps> = ({ label, value, highlight, color }) => (
  <div style={{ flex: '1 1 120px', minWidth: '100px' }}>
    <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '2px' }}>{label}</div>
    <div
      style={{
        fontSize: highlight ? '20px' : '16px',
        fontWeight: highlight ? 700 : 600,
        color: color || (highlight ? '#16a34a' : '#0f172a'),
      }}
    >
      {value}
    </div>
  </div>
);

interface RecommendationCardProps {
  rec: SnapshotRecommendation;
  categoryConfig: { label: string; color: string; bg: string };
}

const RecommendationCard: React.FC<RecommendationCardProps> = ({ rec, categoryConfig }) => {
  const impactConfig = IMPACT_CONFIG[rec.impact] || IMPACT_CONFIG.low;

  return (
    <div
      style={{
        padding: '14px 18px',
        backgroundColor: '#fff',
        border: '1px solid #e2e8f0',
        borderRadius: '8px',
        borderLeft: `4px solid ${categoryConfig.color}`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
        <span style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>{rec.title}</span>
        <span
          style={{
            fontSize: '10px',
            fontWeight: 600,
            padding: '2px 6px',
            borderRadius: '4px',
            backgroundColor: impactConfig.bg,
            color: impactConfig.color,
            textTransform: 'uppercase',
          }}
        >
          {rec.impact}
        </span>
      </div>
      <p style={{ margin: '0 0 8px', fontSize: '13px', color: '#475569', lineHeight: 1.5 }}>
        {rec.description}
      </p>
      {rec.action && (
        <div
          style={{
            fontSize: '12px',
            color: categoryConfig.color,
            fontWeight: 500,
          }}
        >
          Action: {rec.action}
        </div>
      )}
    </div>
  );
};
