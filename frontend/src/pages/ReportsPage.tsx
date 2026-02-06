/**
 * ReportsPage - Calibration and prediction accuracy (PREVIEW-001)
 * Premium feature: view calibration reports for prediction accuracy
 */
import React, { useState, useEffect } from 'react';
import { useEntitlement } from '../hooks/useEntitlement';
import { PreviewBadge } from '../components/shared/PreviewBadge';
import { UpgradeCTA } from '../components/shared/UpgradeCTA';
import { fetchCalibrationReport } from '../services/api';
import type { CalibrationReport, CalibrationMetric } from '../types/plan';
import '../styles/preview.css';

type LoadState = 'idle' | 'loading' | 'loaded' | 'offline' | 'insufficient';

const WINDOW_OPTIONS = [
  { label: '7 Days', value: 7 },
  { label: '14 Days', value: 14 },
  { label: '30 Days', value: 30 },
];

export const ReportsPage: React.FC = () => {
  const { canAccess, isPremium } = useEntitlement();
  const [windowDays, setWindowDays] = useState(14);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [report, setReport] = useState<CalibrationReport | null>(null);

  useEffect(() => {
    if (!canAccess('reports')) return;

    setLoadState('loading');
    fetchCalibrationReport(windowDays)
      .then((data) => {
        if (data) {
          if (data.sample_size < 5) {
            setLoadState('insufficient');
          } else {
            setLoadState('loaded');
          }
          setReport(data);
        } else {
          setLoadState('offline');
        }
      })
      .catch(() => {
        setLoadState('offline');
      });
  }, [windowDays, canAccess]);

  return (
    <div className="page-container" style={{ maxWidth: '1200px' }}>
      <div className="preview-page-header">
        <div>
          <h1>Reports</h1>
          <p className="preview-page-subtitle">Prediction calibration and accuracy metrics</p>
        </div>
        <PreviewBadge variant={isPremium ? 'preview' : 'premium'} />
      </div>

      {!canAccess('reports') ? (
        <UpgradeCTA
          feature="Reports"
          description="Track prediction accuracy across revenue, costs, and profit metrics."
        />
      ) : (
        <div className="preview-layout-full">
          {/* Window Selector */}
          <div style={{ marginBottom: '24px', display: 'flex', gap: '8px' }}>
            {WINDOW_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setWindowDays(opt.value)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: windowDays === opt.value ? '2px solid #2563eb' : '1px solid #e2e8f0',
                  background: windowDays === opt.value ? '#eff6ff' : '#fff',
                  color: windowDays === opt.value ? '#1e40af' : '#334155',
                  fontWeight: 500,
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {loadState === 'loading' ? (
            <div className="preview-loading">Loading calibration report...</div>
          ) : loadState === 'offline' ? (
            <div className="preview-offline">
              Reports service unavailable. The backend may be offline.
            </div>
          ) : loadState === 'insufficient' ? (
            <div className="preview-empty" style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
              <h3>Insufficient Data</h3>
              <p>Need at least 5 completed outcomes for calibration. Current: {report?.sample_size || 0}</p>
            </div>
          ) : report ? (
            <CalibrationResults report={report} />
          ) : null}
        </div>
      )}
    </div>
  );
};

interface CalibrationResultsProps {
  report: CalibrationReport;
}

const CalibrationResults: React.FC<CalibrationResultsProps> = ({ report }) => {
  const accuracyScore = parseFloat(report.accuracy_score);
  const accuracyClass = accuracyScore >= 80 ? 'green' : accuracyScore >= 60 ? 'amber' : 'red';

  return (
    <div>
      {/* Summary Metrics */}
      <div className="preview-metrics" style={{ marginBottom: '24px' }}>
        <div className="preview-metric-card" style={{ background: '#fff' }}>
          <div className="preview-metric-label">Accuracy Score</div>
          <div className={`preview-metric-value ${accuracyClass}`}>
            {accuracyScore.toFixed(0)}%
          </div>
          <div className="preview-metric-delta">
            Based on {report.sample_size} outcomes
          </div>
        </div>
        <div className="preview-metric-card" style={{ background: '#fff' }}>
          <div className="preview-metric-label">Window</div>
          <div className="preview-metric-value" style={{ fontSize: '20px' }}>
            {report.window_days} days
          </div>
          <div className="preview-metric-delta">
            Computed: {new Date(report.computed_at).toLocaleDateString()}
          </div>
        </div>
      </div>

      {/* Per-Metric Breakdown */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 style={{ margin: '0 0 16px', fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>
          Metric Accuracy
        </h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Predicted Avg</th>
              <th>Actual Avg</th>
              <th>MAE</th>
              <th>Variance %</th>
              <th>Direction</th>
            </tr>
          </thead>
          <tbody>
            {report.metrics.map((m: CalibrationMetric) => (
              <tr key={m.name}>
                <td className="td-bold" style={{ textTransform: 'capitalize' }}>
                  {m.name.replace(/_/g, ' ')}
                </td>
                <td className="td-mono">{m.predicted_avg}</td>
                <td className="td-mono">{m.actual_avg}</td>
                <td className="td-mono">{m.mae}</td>
                <td className="td-mono">
                  <span style={{ color: parseFloat(m.mean_variance_pct) > 20 ? '#dc2626' : '#059669' }}>
                    {m.mean_variance_pct}%
                  </span>
                </td>
                <td>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 500,
                      backgroundColor: m.direction === 'accurate' ? '#d1fae5' : m.direction === 'over' ? '#fee2e2' : '#dbeafe',
                      color: m.direction === 'accurate' ? '#065f46' : m.direction === 'over' ? '#991b1b' : '#1e40af',
                    }}
                  >
                    {m.direction === 'accurate' ? 'Accurate' : m.direction === 'over' ? 'Over-predicting' : 'Under-predicting'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Insights */}
      {report.insights && report.insights.length > 0 && (
        <div className="preview-section">
          <div className="preview-section-header">Insights</div>
          <ul className="preview-insights">
            {report.insights.map((insight, i) => (
              <li key={i} className="preview-insight info">{insight}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
