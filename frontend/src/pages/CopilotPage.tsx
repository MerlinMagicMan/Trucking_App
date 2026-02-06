/**
 * CopilotPage - Plan degradation monitor (PREVIEW-001)
 * Premium feature: shows degradation signals and suggestions for selected plan
 */
import React, { useState, useEffect } from 'react';
import { useEntitlement } from '../hooks/useEntitlement';
import { PreviewBadge } from '../components/shared/PreviewBadge';
import { UpgradeCTA } from '../components/shared/UpgradeCTA';
import { fetchPlanHistory } from '../services/api';
import { fetchPlanStatus } from '../services/copilot';
import type { PlanHistoryItem } from '../types/org';
import type { CopilotResponse, Signal, Suggestion } from '../types/copilot';
import '../styles/preview.css';

type LoadState = 'idle' | 'loading' | 'loaded' | 'offline';

export const CopilotPage: React.FC = () => {
  const { canAccess, isPremium } = useEntitlement();
  const [plans, setPlans] = useState<PlanHistoryItem[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [copilotData, setCopilotData] = useState<CopilotResponse | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [plansLoading, setPlansLoading] = useState(true);

  // Load plan history for selection
  useEffect(() => {
    fetchPlanHistory()
      .then((data) => {
        setPlans(data);
        setPlansLoading(false);
      })
      .catch(() => {
        setPlans([]);
        setPlansLoading(false);
      });
  }, []);

  // Fetch copilot data when plan selected (premium only)
  useEffect(() => {
    if (!selectedPlanId || !canAccess('copilot')) {
      setCopilotData(null);
      return;
    }

    setLoadState('loading');
    fetchPlanStatus(selectedPlanId)
      .then((data) => {
        if (data) {
          setCopilotData(data);
          setLoadState('loaded');
        } else {
          setLoadState('offline');
        }
      })
      .catch(() => {
        setLoadState('offline');
      });
  }, [selectedPlanId, canAccess]);

  return (
    <div className="page-container" style={{ maxWidth: '1400px' }}>
      <div className="preview-page-header">
        <div>
          <h1>Copilot</h1>
          <p className="preview-page-subtitle">Plan degradation monitoring and suggestions</p>
        </div>
        <PreviewBadge variant={isPremium ? 'preview' : 'premium'} />
      </div>

      {!canAccess('copilot') ? (
        <UpgradeCTA
          feature="Copilot"
          description="Monitor plan health in real-time with degradation signals and actionable suggestions."
        />
      ) : (
        <div className="preview-layout">
          {/* Sidebar: Plan selector */}
          <div className="preview-sidebar">
            <div className="preview-section-header">Select a Plan</div>
            {plansLoading ? (
              <div className="preview-loading">Loading plans...</div>
            ) : plans.length === 0 ? (
              <div className="preview-empty">
                <p>No plans found. Generate plans in Preflight first.</p>
              </div>
            ) : (
              <ul className="preview-list">
                {plans.slice(0, 20).map((plan) => (
                  <li
                    key={plan.id}
                    className="preview-list-item"
                    style={{
                      cursor: 'pointer',
                      background: selectedPlanId === `plan-${plan.id}` ? '#eff6ff' : undefined,
                      borderRadius: '6px',
                      padding: '10px',
                      marginBottom: '4px',
                    }}
                    onClick={() => setSelectedPlanId(`plan-${plan.id}`)}
                  >
                    <div>
                      <div style={{ fontWeight: 500, fontSize: '13px' }}>
                        Plan #{plan.id}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>
                        {new Date(plan.timestamp).toLocaleString()}
                      </div>
                      <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                        {plan.plans_generated} plans · {plan.loads_analyzed || 0} loads
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Main: Copilot results */}
          <div className="preview-main">
            {!selectedPlanId ? (
              <div className="preview-empty">
                <h3>Select a Plan</h3>
                <p>Choose a plan from the list to view copilot analysis</p>
              </div>
            ) : loadState === 'loading' ? (
              <div className="preview-loading">Analyzing plan...</div>
            ) : loadState === 'offline' ? (
              <div className="preview-offline">
                Copilot service unavailable. The backend may be offline.
              </div>
            ) : copilotData ? (
              <CopilotResults data={copilotData} />
            ) : (
              <div className="preview-empty">
                <p>No copilot data available for this plan.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

interface CopilotResultsProps {
  data: CopilotResponse;
}

const CopilotResults: React.FC<CopilotResultsProps> = ({ data }) => {
  const statusColors: Record<string, { bg: string; color: string }> = {
    ok: { bg: '#d1fae5', color: '#065f46' },
    degraded: { bg: '#fef3c7', color: '#92400e' },
    unknown: { bg: '#f1f5f9', color: '#475569' },
  };

  const statusStyle = statusColors[data.status] || statusColors.unknown;

  return (
    <div>
      {/* Status Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <span
            style={{
              padding: '6px 16px',
              borderRadius: '20px',
              fontSize: '14px',
              fontWeight: 600,
              textTransform: 'uppercase',
              backgroundColor: statusStyle.bg,
              color: statusStyle.color,
            }}
          >
            {data.status}
          </span>
          <span style={{ fontSize: '13px', color: '#64748b' }}>
            {data.signals.length} signal{data.signals.length !== 1 ? 's' : ''} ·{' '}
            {data.suggestions.length} suggestion{data.suggestions.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div style={{ fontSize: '12px', color: '#94a3b8' }}>
          Evaluated at {new Date(data.meta.evaluated_at).toLocaleString()}
        </div>
      </div>

      {/* Signals */}
      {data.signals.length > 0 && (
        <div className="preview-section">
          <div className="preview-section-header">Degradation Signals</div>
          {data.signals.map((signal, i) => (
            <SignalCard key={i} signal={signal} />
          ))}
        </div>
      )}

      {/* Suggestions */}
      {data.suggestions.length > 0 && (
        <div className="preview-section">
          <div className="preview-section-header">Suggestions</div>
          {data.suggestions.map((suggestion, i) => (
            <SuggestionCard key={i} suggestion={suggestion} />
          ))}
        </div>
      )}

      {/* Explanations */}
      {data.explanations.length > 0 && (
        <div className="preview-section">
          <div className="preview-section-header">Analysis</div>
          <ul className="preview-insights">
            {data.explanations.map((exp, i) => (
              <li key={i} className="preview-insight info">
                {exp}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Trust Info */}
      {data.meta.trust && (
        <div className="preview-section">
          <div className="preview-section-header">Trust Assessment</div>
          <div className="preview-metrics">
            <div className="preview-metric-card">
              <div className="preview-metric-label">Confidence Score</div>
              <div className={`preview-metric-value ${data.meta.trust.confidence_score >= 80 ? 'green' : data.meta.trust.confidence_score >= 55 ? 'amber' : 'red'}`}>
                {data.meta.trust.confidence_score}
              </div>
            </div>
            <div className="preview-metric-card">
              <div className="preview-metric-label">Confidence Level</div>
              <div className="preview-metric-value" style={{ fontSize: '20px', textTransform: 'uppercase' }}>
                {data.meta.trust.confidence_label}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const SignalCard: React.FC<{ signal: Signal }> = ({ signal }) => {
  const severityColors: Record<string, { bg: string; color: string }> = {
    high: { bg: '#fee2e2', color: '#991b1b' },
    medium: { bg: '#fef3c7', color: '#92400e' },
    low: { bg: '#dbeafe', color: '#1e40af' },
  };

  const style = severityColors[signal.severity] || severityColors.low;

  return (
    <div
      style={{
        padding: '16px',
        backgroundColor: '#f8fafc',
        border: '1px solid #e2e8f0',
        borderRadius: '8px',
        marginBottom: '8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        <span
          style={{
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 600,
            textTransform: 'uppercase',
            backgroundColor: style.bg,
            color: style.color,
          }}
        >
          {signal.severity}
        </span>
        <span style={{ fontSize: '12px', color: '#64748b', fontFamily: 'monospace' }}>
          {signal.kind}
        </span>
      </div>
      <div style={{ fontSize: '14px', color: '#0f172a' }}>{signal.summary}</div>
    </div>
  );
};

const SuggestionCard: React.FC<{ suggestion: Suggestion }> = ({ suggestion }) => {
  return (
    <div
      style={{
        padding: '16px',
        backgroundColor: '#faf5ff',
        border: '1px solid #e9d5ff',
        borderRadius: '8px',
        marginBottom: '8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        <span
          style={{
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 600,
            textTransform: 'uppercase',
            backgroundColor: '#f3e8ff',
            color: '#7c3aed',
          }}
        >
          {suggestion.kind.replace('_', ' ')}
        </span>
      </div>
      <div style={{ fontSize: '14px', fontWeight: 500, color: '#0f172a', marginBottom: '4px' }}>
        {suggestion.summary}
      </div>
      <div style={{ fontSize: '13px', color: '#64748b' }}>{suggestion.rationale}</div>
    </div>
  );
};

export default CopilotPage;
