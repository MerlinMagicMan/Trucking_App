import React, { useEffect, useState } from 'react';
import type { PlanHistoryItem, PlanHistoryDetail } from '../types/org';
import { fetchPlanHistory, fetchPlanHistoryDetail } from '../services/api';

export const PlanHistoryPage: React.FC = () => {
  const [items, setItems] = useState<PlanHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<PlanHistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchPlanHistory()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  const handleView = async (id: number) => {
    if (detail?.id === id) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const d = await fetchPlanHistoryDetail(id);
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

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1>Plans History</h1>
          <p className="page-subtitle">{items.length} generation event{items.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

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
                      </tr>
                    </thead>
                    <tbody>
                      {detail.full_payload.response.plans.map((plan: any, i: number) => (
                        <tr key={i}>
                          <td className="td-bold">Plan {i + 1}</td>
                          <td>{plan.num_loads}</td>
                          <td className="td-green">${plan.profit_per_day_usd?.toFixed(0)}</td>
                          <td>${plan.net_profit_usd?.toFixed(0)}</td>
                          <td>${plan.total_revenue_usd?.toFixed(0)}</td>
                          <td>{plan.end_location}</td>
                          <td>{plan.confidence}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
