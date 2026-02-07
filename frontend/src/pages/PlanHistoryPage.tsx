import React, { useEffect, useState } from 'react';
import type { PlanHistoryItem, PlanHistoryDetail } from '../types/org';
import type { OutcomeSummaryItem, CalibrationReport } from '../types/plan';
import { getDataClient } from '../services/dataClient';

const VarianceBadge: React.FC<{ pct: string | null | undefined }> = ({ pct }) => {
  if (pct == null) return <span style={{ color: '#94a3b8', fontSize: '12px' }}>—</span>;
  const num = parseFloat(pct);
  const abs = Math.abs(num);
  let color = '#16a34a'; // green
  if (abs > 25) color = '#dc2626'; // red
  else if (abs > 10) color = '#d97706'; // amber
  const sign = num > 0 ? '+' : '';
  return (
    <span style={{
      fontSize: '12px',
      fontWeight: 600,
      color,
      padding: '2px 6px',
      borderRadius: '4px',
      background: `${color}14`,
    }}>
      {sign}{num.toFixed(1)}%
    </span>
  );
};

export const PlanHistoryPage: React.FC = () => {
  const [items, setItems] = useState<PlanHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<PlanHistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [outcomes, setOutcomes] = useState<OutcomeSummaryItem[]>([]);
  const [calibration, setCalibration] = useState<CalibrationReport | null>(null);

  useEffect(() => {
    const client = getDataClient();
    client.getPlanHistory()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
    client.getOutcomeSummary(50).then(setOutcomes).catch(() => setOutcomes([]));
    client.getCalibrationReport(30).then(setCalibration).catch(() => setCalibration(null));
  }, []);

  const handleView = async (id: number) => {
    if (detail?.id === id) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const d = await getDataClient().getPlanHistoryDetail(id);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });

  // Build a map of plan_id -> outcome for quick lookup
  const outcomeByPlanId = React.useMemo(() => {
    const map = new Map<string, OutcomeSummaryItem>();
    for (const o of outcomes) {
      map.set(o.plan_id, o);
    }
    return map;
  }, [outcomes]);

  // Get all plan_ids from detail payload for outcome lookup
  const getDetailPlanIds = (): string[] => {
    if (!detail?.full_payload?.response?.plans) return [];
    return detail.full_payload.response.plans.map((p: any) => p.plan_id).filter(Boolean);
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1>Plans History</h1>
          <p className="page-subtitle">{items.length} generation event{items.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {/* Calibration summary */}
      {calibration && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0 }}>Prediction Calibration</h2>
            <span style={{
              fontSize: '13px',
              fontWeight: 700,
              padding: '3px 10px',
              borderRadius: '12px',
              background: parseFloat(calibration.accuracy_score) >= 80 ? '#dcfce7'
                : parseFloat(calibration.accuracy_score) >= 60 ? '#fef3c7' : '#fee2e2',
              color: parseFloat(calibration.accuracy_score) >= 80 ? '#166534'
                : parseFloat(calibration.accuracy_score) >= 60 ? '#92400e' : '#991b1b',
            }}>
              {parseFloat(calibration.accuracy_score).toFixed(0)}% accuracy
            </span>
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>
              {calibration.sample_size} outcomes · {calibration.window_days}d window
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '12px' }}>
            {calibration.metrics.map((m) => {
              const pct = parseFloat(m.mean_variance_pct);
              const absPct = Math.abs(pct);
              const barColor = absPct > 15 ? '#dc2626' : absPct > 5 ? '#d97706' : '#16a34a';
              const arrow = m.direction === 'over' ? '↑' : m.direction === 'under' ? '↓' : '→';
              return (
                <div key={m.name} style={{
                  flex: '1 1 160px', padding: '8px 12px', background: '#f8fafc',
                  borderRadius: '6px', fontSize: '13px',
                }}>
                  <div style={{ fontWeight: 600, marginBottom: '4px', textTransform: 'capitalize' }}>
                    {m.name.replace('_', ' ')}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ color: barColor, fontWeight: 700 }}>
                      {arrow} {pct > 0 ? '+' : ''}{pct.toFixed(1)}%
                    </span>
                    <span style={{ color: '#64748b', fontSize: '11px' }}>
                      MAE {parseFloat(m.mae).toFixed(0)}
                    </span>
                  </div>
                  <div style={{
                    marginTop: '4px', height: '4px', borderRadius: '2px',
                    background: '#e2e8f0', overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', borderRadius: '2px', background: barColor,
                      width: `${Math.min(absPct * 4, 100)}%`,
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: '12px', color: '#475569' }}>
            {calibration.insights.map((insight, i) => (
              <div key={i} style={{ marginBottom: '2px' }}>· {insight}</div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="empty-state"><p>Loading history...</p></div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <h2>No plan history yet</h2>
          <p>Generate plans from Preflight to see history here.</p>
        </div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Horizon</th>
                <th>Plans</th>
                <th>Loads Analyzed</th>
                <th>Time (ms)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className={detail?.id === item.id ? 'active-row' : ''}>
                  <td className="td-bold">{formatDate(item.timestamp)}</td>
                  <td>{item.planning_horizon_days}d</td>
                  <td>{item.plans_generated}</td>
                  <td>{item.loads_analyzed ?? '—'}</td>
                  <td className="td-mono">{item.execution_time_ms ?? '—'}</td>
                  <td>
                    <button className="btn btn-sm" onClick={() => handleView(item.id)} type="button">
                      {detail?.id === item.id ? 'Close' : 'View'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Replay detail panel */}
          {detailLoading && <div className="empty-state"><p>Loading details...</p></div>}
          {detail && !detailLoading && (
            <div className="card" style={{ marginTop: '20px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 12px' }}>
                Plan Generation — {formatDate(detail.timestamp)}
              </h2>
              <div className="history-meta">
                <div><strong>Horizon:</strong> {detail.planning_horizon_days}d</div>
                <div><strong>Plans:</strong> {detail.plans_generated}</div>
                <div><strong>Loads:</strong> {detail.loads_analyzed ?? '—'}</div>
                <div><strong>Snapshot:</strong> {String(detail.snapshot_id).slice(0, 8)}...</div>
              </div>

              {detail.full_payload?.response?.plans && (
                <div>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '16px 0 8px' }}>Plans Generated</h3>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Plan</th>
                        <th>Loads</th>
                        <th>Profit/Day</th>
                        <th>Net Profit</th>
                        <th>Revenue</th>
                        <th>End Location</th>
                        <th>Confidence</th>
                        <th>Outcome</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.full_payload.response.plans.map((plan: any, i: number) => {
                        const outcome = plan.plan_id ? outcomeByPlanId.get(plan.plan_id) : undefined;
                        return (
                          <tr key={i}>
                            <td className="td-bold">Plan {i + 1}</td>
                            <td>{plan.num_loads}</td>
                            <td className="td-green">${plan.profit_per_day_usd?.toFixed(0)}</td>
                            <td>${plan.net_profit_usd?.toFixed(0)}</td>
                            <td>${plan.total_revenue_usd?.toFixed(0)}</td>
                            <td>{plan.end_location}</td>
                            <td>{plan.confidence}</td>
                            <td>
                              {outcome ? (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span style={{
                                    fontSize: '11px',
                                    padding: '1px 5px',
                                    borderRadius: '3px',
                                    background: outcome.status === 'complete' ? '#dcfce7' : outcome.status === 'partial' ? '#fef3c7' : '#f1f5f9',
                                    color: outcome.status === 'complete' ? '#166534' : outcome.status === 'partial' ? '#92400e' : '#64748b',
                                  }}>
                                    {outcome.status}
                                  </span>
                                  <VarianceBadge pct={outcome.profit_variance_pct} />
                                </div>
                              ) : (
                                <span style={{ color: '#94a3b8', fontSize: '12px' }}>—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Outcome variance detail */}
              {getDetailPlanIds().some(pid => outcomeByPlanId.has(pid)) && (
                <div style={{ marginTop: '16px' }}>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 8px' }}>Outcome Variances</h3>
                  {getDetailPlanIds().filter(pid => outcomeByPlanId.has(pid)).map((pid) => {
                    const o = outcomeByPlanId.get(pid)!;
                    return (
                      <div key={pid} style={{
                        display: 'flex', gap: '16px', alignItems: 'center',
                        padding: '8px 12px', background: '#f8fafc', borderRadius: '6px', marginBottom: '6px',
                        fontSize: '13px',
                      }}>
                        <span style={{ fontWeight: 600, minWidth: '80px' }}>{pid.slice(0, 8)}...</span>
                        <span>Est: ${o.predicted_net_profit ?? '—'}</span>
                        <span>Actual: ${o.actual_net_profit ?? '—'}</span>
                        <span>Profit: <VarianceBadge pct={o.profit_variance_pct} /></span>
                        <span>Time: <VarianceBadge pct={o.time_variance_pct} /></span>
                      </div>
                    );
                  })}
                </div>
              )}

              {detail.warnings && detail.warnings.length > 0 && (
                <div style={{ marginTop: '12px' }}>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 8px' }}>Warnings</h3>
                  {detail.warnings.map((w: string, i: number) => (
                    <div key={i} style={{ fontSize: '13px', color: '#dc2626', marginBottom: '4px' }}>{w}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};
