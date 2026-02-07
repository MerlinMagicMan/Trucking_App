/**
 * Truck Snapshot Page (Wave 2: Snapshot Flow)
 *
 * Select a plan from history and generate a snapshot with recommendations.
 * Works fully offline in demo mode.
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDataClient } from '../services/dataClient';
import {
  saveActiveSnapshot,
  generateRecommendations,
  generateProjections,
  generateLaneInsights,
  type ActiveSnapshot,
} from '../services/snapshotStorage';
import type { PlanHistoryItem } from '../types/org';
import type { Plan } from '../types/plan';

interface StoredPlanDetail {
  plans?: Plan[];
  response?: { plans?: Plan[] };
}

export default function TruckSnapshotPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<PlanHistoryItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null);
  const [availablePlans, setAvailablePlans] = useState<Plan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);

  // Load plan history on mount
  useEffect(() => {
    const client = getDataClient();
    client
      .getPlanHistory()
      .then((items) => {
        setHistoryItems(items);
        // Auto-select first history item if available
        if (items.length > 0) {
          setSelectedHistoryId(items[0].id);
        }
      })
      .catch(() => {
        setError('Failed to load plan history');
      })
      .finally(() => setLoading(false));
  }, []);

  // Load plans when history item is selected
  useEffect(() => {
    if (!selectedHistoryId) {
      setAvailablePlans([]);
      setSelectedPlanId(null);
      return;
    }

    const client = getDataClient();
    client
      .getPlanHistoryDetail(selectedHistoryId)
      .then((detail) => {
        // Extract plans from full_payload
        const payload = detail.full_payload as StoredPlanDetail | null;
        const plans = payload?.plans || payload?.response?.plans || [];
        setAvailablePlans(plans);
        // Auto-select first plan
        if (plans.length > 0) {
          setSelectedPlanId(plans[0].plan_id);
        } else {
          setSelectedPlanId(null);
        }
      })
      .catch(() => {
        setAvailablePlans([]);
        setSelectedPlanId(null);
      });
  }, [selectedHistoryId]);

  const handleGenerateSnapshot = async () => {
    if (!selectedPlanId) {
      setError('Please select a plan');
      return;
    }

    const selectedPlan = availablePlans.find((p) => p.plan_id === selectedPlanId);
    if (!selectedPlan) {
      setError('Selected plan not found');
      return;
    }

    setGenerating(true);
    setError(null);

    try {
      const client = getDataClient();

      // Try to get trust report (may fail in demo without decision)
      let trustScore: number | null = null;
      let trustLabel: string | null = null;
      let trustWarnings = 0;

      try {
        const trustReport = await client.getTrustReport(selectedPlanId);
        if (trustReport) {
          trustScore = trustReport.confidence_score;
          trustLabel = trustReport.confidence_label;
          trustWarnings = trustReport.warnings?.length || 0;
        }
      } catch {
        // Trust report not available, continue without it
      }

      // Build plan summary
      const planSummary: ActiveSnapshot['plan_summary'] = {
        total_revenue: selectedPlan.total_revenue_usd,
        total_costs: selectedPlan.total_costs_usd,
        net_profit: selectedPlan.net_profit_usd,
        profit_per_day: selectedPlan.profit_per_day_usd,
        num_loads: selectedPlan.loads.length,
        end_location: selectedPlan.end_location_name,
        confidence: selectedPlan.confidence,
      };

      // Generate deterministic recommendations and projections
      const recommendations = generateRecommendations(planSummary, trustScore);
      const projections = generateProjections(planSummary);
      const laneInsights = generateLaneInsights(planSummary);

      // Create and save snapshot
      const snapshot: ActiveSnapshot = {
        id: crypto.randomUUID(),
        created_at: new Date().toISOString(),
        plan_id: selectedPlanId,
        plan_summary: planSummary,
        trust_score: trustScore,
        trust_label: trustLabel,
        trust_warnings: trustWarnings,
        recommendations,
        projections,
        lane_repeat_insights: laneInsights,
      };

      saveActiveSnapshot(snapshot);

      // Navigate to recommendations
      navigate('/recommendations');
    } catch (e: any) {
      setError(e?.message || 'Failed to generate snapshot');
    } finally {
      setGenerating(false);
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });

  if (loading) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1>Generate Snapshot</h1>
        </div>
        <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
          Loading plan history...
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: '900px' }}>
      <div className="page-header">
        <div>
          <h1>Generate Snapshot</h1>
          <p className="page-subtitle">
            Select a plan to generate recommendations and forward-look projections
          </p>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '6px',
            marginBottom: '16px',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            fontSize: '13px',
          }}
        >
          {error}
        </div>
      )}

      {historyItems.length === 0 ? (
        <div
          style={{
            padding: '40px',
            textAlign: 'center',
            backgroundColor: '#f8fafc',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
          }}
        >
          <h3 style={{ margin: '0 0 8px', fontSize: '18px', color: '#334155' }}>
            No Plan History
          </h3>
          <p style={{ margin: '0 0 16px', color: '#64748b', fontSize: '14px' }}>
            Generate plans from Preflight first, then return here to create a snapshot.
          </p>
          <button
            onClick={() => navigate('/plans')}
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
            Go to Preflight
          </button>
        </div>
      ) : (
        <>
          {/* History Selection */}
          <div className="settings-section" style={{ marginBottom: '24px' }}>
            <h3 className="settings-section-title">1. Select Plan Generation</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {historyItems.slice(0, 10).map((item) => (
                <label
                  key={item.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px 16px',
                    backgroundColor: selectedHistoryId === item.id ? '#eff6ff' : '#f8fafc',
                    border: `1px solid ${selectedHistoryId === item.id ? '#3b82f6' : '#e2e8f0'}`,
                    borderRadius: '6px',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="radio"
                    name="historyItem"
                    checked={selectedHistoryId === item.id}
                    onChange={() => setSelectedHistoryId(item.id)}
                    style={{ accentColor: '#3b82f6' }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: '14px', color: '#0f172a' }}>
                      {formatDate(item.timestamp)}
                    </div>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>
                      {item.plans_generated} plans · {item.planning_horizon_days}d horizon
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Plan Selection */}
          {availablePlans.length > 0 && (
            <div className="settings-section" style={{ marginBottom: '24px' }}>
              <h3 className="settings-section-title">2. Select Plan</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {availablePlans.map((plan, i) => (
                  <label
                    key={plan.plan_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '12px 16px',
                      backgroundColor: selectedPlanId === plan.plan_id ? '#f0fdf4' : '#f8fafc',
                      border: `1px solid ${selectedPlanId === plan.plan_id ? '#22c55e' : '#e2e8f0'}`,
                      borderRadius: '6px',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      name="plan"
                      checked={selectedPlanId === plan.plan_id}
                      onChange={() => setSelectedPlanId(plan.plan_id)}
                      style={{ accentColor: '#22c55e' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>
                          Plan {i + 1}
                        </span>
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            backgroundColor:
                              plan.confidence === 'high'
                                ? '#dcfce7'
                                : plan.confidence === 'medium'
                                  ? '#fef3c7'
                                  : '#fee2e2',
                            color:
                              plan.confidence === 'high'
                                ? '#166534'
                                : plan.confidence === 'medium'
                                  ? '#92400e'
                                  : '#991b1b',
                          }}
                        >
                          {plan.confidence}
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                        ${plan.profit_per_day_usd.toFixed(0)}/day · {plan.loads.length} loads · ends at{' '}
                        {plan.end_location_name}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 700, fontSize: '16px', color: '#16a34a' }}>
                        ${plan.net_profit_usd.toFixed(0)}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>net profit</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Generate Button */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={handleGenerateSnapshot}
              disabled={!selectedPlanId || generating}
              style={{
                padding: '12px 24px',
                backgroundColor: selectedPlanId ? '#3b82f6' : '#94a3b8',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: selectedPlanId ? 'pointer' : 'not-allowed',
                opacity: generating ? 0.7 : 1,
              }}
            >
              {generating ? 'Generating...' : 'Generate Snapshot'}
            </button>
            <button
              onClick={() => navigate('/plans')}
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
              Back to Preflight
            </button>
          </div>
        </>
      )}
    </div>
  );
}
