/**
 * Forward Look Page (Wave 2: Snapshot Flow)
 *
 * Shows scenario projections and lane repeat insights from the active snapshot.
 * Works fully offline with localStorage persistence.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { getActiveSnapshot, type SnapshotProjection } from '../services/snapshotStorage';

const SCENARIO_CONFIG: Record<
  SnapshotProjection['scenario'],
  { label: string; color: string; bg: string; icon: string }
> = {
  best: { label: 'Best Case', color: '#16a34a', bg: '#dcfce7', icon: '↑' },
  base: { label: 'Base Case', color: '#1d4ed8', bg: '#eff6ff', icon: '→' },
  worst: { label: 'Worst Case', color: '#dc2626', bg: '#fee2e2', icon: '↓' },
};

export default function ForwardLookPage() {
  const navigate = useNavigate();
  const snapshot = getActiveSnapshot();

  if (!snapshot) {
    return (
      <div className="page-container" style={{ maxWidth: '900px' }}>
        <div className="page-header">
          <h1>Forward Look</h1>
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
            Generate a snapshot first to see forward-look projections.
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

  return (
    <div className="page-container" style={{ maxWidth: '1100px' }}>
      <div className="page-header">
        <div>
          <h1>Forward Look</h1>
          <p className="page-subtitle">
            Scenario projections and lane insights for {snapshot.plan_summary.end_location}
          </p>
        </div>
      </div>

      {/* Scenario Projections */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px', color: '#0f172a' }}>
          Profit Scenarios
        </h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '16px',
          }}
        >
          {snapshot.projections.map((proj) => {
            const config = SCENARIO_CONFIG[proj.scenario];
            return (
              <div
                key={proj.scenario}
                style={{
                  padding: '20px',
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  borderTop: `4px solid ${config.color}`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                  <span
                    style={{
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: config.bg,
                      color: config.color,
                      borderRadius: '8px',
                      fontSize: '18px',
                      fontWeight: 700,
                    }}
                  >
                    {config.icon}
                  </span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>
                      {config.label}
                    </div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>
                      {proj.probability}% probability
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    fontSize: '28px',
                    fontWeight: 700,
                    color: config.color,
                    marginBottom: '8px',
                  }}
                >
                  ${proj.profit_per_day}/day
                </div>

                <p style={{ margin: 0, fontSize: '13px', color: '#475569', lineHeight: 1.5 }}>
                  {proj.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Lane Repeat Insights */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px', color: '#0f172a' }}>
          If You Repeat This Lane...
        </h2>
        <div
          style={{
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            padding: '20px',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {snapshot.lane_repeat_insights.map((insight, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                }}
              >
                <span
                  style={{
                    width: '24px',
                    height: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: '#eff6ff',
                    color: '#1d4ed8',
                    borderRadius: '50%',
                    fontSize: '12px',
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
                >
                  {i + 1}
                </span>
                <p style={{ margin: 0, fontSize: '14px', color: '#334155', lineHeight: 1.6 }}>
                  {insight}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Historical Context */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px', color: '#0f172a' }}>
          Plan Context
        </h2>
        <div
          style={{
            display: 'flex',
            gap: '16px',
            flexWrap: 'wrap',
          }}
        >
          <ContextCard
            label="Net Profit Target"
            value={`$${snapshot.plan_summary.net_profit.toFixed(0)}`}
          />
          <ContextCard
            label="Daily Earnings Goal"
            value={`$${snapshot.plan_summary.profit_per_day.toFixed(0)}`}
          />
          <ContextCard label="Load Count" value={String(snapshot.plan_summary.num_loads)} />
          <ContextCard label="Confidence" value={snapshot.plan_summary.confidence.toUpperCase()} />
          {snapshot.trust_score !== null && snapshot.trust_score !== undefined && (
            <ContextCard
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
      </div>

      {/* Navigation */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          paddingTop: '24px',
          borderTop: '1px solid #e2e8f0',
        }}
      >
        <button
          onClick={() => navigate('/recommendations')}
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
          ← Back to Recommendations
        </button>
        <button
          onClick={() => navigate('/plans')}
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
          New Plan Search
        </button>
      </div>
    </div>
  );
}

interface ContextCardProps {
  label: string;
  value: string;
  color?: string;
}

const ContextCard: React.FC<ContextCardProps> = ({ label, value, color }) => (
  <div
    style={{
      flex: '1 1 140px',
      padding: '14px 18px',
      backgroundColor: '#fff',
      border: '1px solid #e2e8f0',
      borderRadius: '8px',
      minWidth: '120px',
    }}
  >
    <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '4px' }}>{label}</div>
    <div style={{ fontSize: '18px', fontWeight: 600, color: color || '#0f172a' }}>{value}</div>
  </div>
);
