import React, { useState, useEffect, useCallback } from 'react';
import type { Plan, PreflightPreferences, GeneratePlansResponse, GeneratePlansRequest } from '../types/plan';
import { getDataClient } from '../services/dataClient';
import { PreflightSetup } from '../components/preflight/PreflightSetup';
import { PreflightResults } from '../components/preflight/PreflightResults';
import { ComparePanel } from '../components/preflight/ComparePanel';
import { InspectPanelInline } from '../components/preflight/InspectPanel';
import { rankPlans } from '../services/planRanking';
import { generatePlanExplanation } from '../services/planExplanation';
import '../styles/preflight.css';

/**
 * Preflight ranking adapter (NEXT-002 E2):
 * If plans already have ranking_breakdown (demo mode), only fill missing explanation.
 * If plans lack ranking_breakdown (live mode), rank + explain.
 */
function ensureRanked(plans: Plan[]): Plan[] {
  if (plans.length === 0) return plans;

  const needsRanking = !plans[0].ranking_breakdown;

  if (needsRanking) {
    const ranked = rankPlans(plans);
    ranked.forEach((plan, i) => {
      if (plan.ranking_breakdown && !plan.ranking_explanation) {
        plan.ranking_explanation = generatePlanExplanation(plan, plan.ranking_breakdown, i + 1);
      }
    });
    return ranked;
  }

  // Already ranked — only fill missing explanations
  return plans.map((plan, i) => {
    if (plan.ranking_breakdown && !plan.ranking_explanation) {
      return {
        ...plan,
        ranking_explanation: generatePlanExplanation(plan, plan.ranking_breakdown, i + 1),
      };
    }
    return plan;
  });
}

export const PreflightPage: React.FC = () => {
  const [response, setResponse] = useState<GeneratePlansResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [inspectedPlan, setInspectedPlan] = useState<Plan | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'compare'>('list');

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!response?.plans.length) return;
    const currentIndex = inspectedPlan
      ? response.plans.findIndex(p => p.plan_id === inspectedPlan.plan_id)
      : -1;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = currentIndex < response.plans.length - 1 ? currentIndex + 1 : 0;
      setInspectedPlan(response.plans[nextIndex]);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = currentIndex > 0 ? currentIndex - 1 : response.plans.length - 1;
      setInspectedPlan(response.plans[prevIndex]);
    } else if (e.key === '1' || e.key === '2' || e.key === '3') {
      const idx = parseInt(e.key) - 1;
      if (idx < response.plans.length) {
        setInspectedPlan(response.plans[idx]);
      }
    }
  }, [response, inspectedPlan]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleSubmit = async (prefs: PreflightPreferences) => {
    setLoading(true);
    setError(null);

    try {
      const request: GeneratePlansRequest = {
        current_lat: prefs.current_lat,
        current_lng: prefs.current_lng,
        hos: prefs.hos || {
          drive_remaining_min: 660,
          on_duty_remaining_min: 840,
          cycle_remaining_min: 4200,
        },
        planning_horizon_days: prefs.planning_horizon_days,
        max_plans: 3,
        radius_miles: 250,
      };

      const result = await getDataClient().generatePlans(request);

      // NEXT-002 E2: Preflight-layer ranking adapter
      result.plans = ensureRanked(result.plans);

      setResponse(result);
      setLastUpdated(new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }));
      // Default to compare if 3+ plans, list otherwise
      setViewMode(result.plans.length >= 3 ? 'compare' : 'list');
      // Auto-select first plan on generate
      if (result.plans.length > 0) {
        setInspectedPlan(result.plans[0]);
      }
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Failed to generate plans.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleInspect = (plan: Plan) => {
    setInspectedPlan(plan);
  };

  const handleCloseInspect = () => {
    setInspectedPlan(null);
  };

  const showCompareToggle = response && response.plans.length >= 2;

  return (
    <div className={`pf-workspace ${inspectedPlan ? 'has-inspect' : ''}`}>
      <PreflightSetup
        onSubmit={handleSubmit}
        loading={loading}
        lastUpdated={lastUpdated}
        planCount={response?.plans.length}
        loadsAnalyzed={response?.plans[0]?.loads_analyzed}
      />

      <div className="pf-canvas">
        {error && (
          <div className="pf-error" style={{ margin: '16px' }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* View mode toggle */}
        {showCompareToggle && (
          <div style={{ display: 'flex', gap: '4px', marginBottom: '12px' }}>
            <button
              className={`pf-horizon-btn ${viewMode === 'list' ? 'active' : ''}`}
              onClick={() => setViewMode('list')}
              type="button"
            >
              List
            </button>
            <button
              className={`pf-horizon-btn ${viewMode === 'compare' ? 'active' : ''}`}
              onClick={() => setViewMode('compare')}
              type="button"
            >
              Compare
            </button>
          </div>
        )}

        {viewMode === 'compare' && response && response.plans.length >= 2 ? (
          <>
            {response.warnings.length > 0 && (
              <div className="pf-warnings">
                {response.warnings.map((w, i) => (
                  <div key={i} className="pf-warning">{w}</div>
                ))}
              </div>
            )}
            <ComparePanel plans={response.plans} onSelectPlan={handleInspect} />
          </>
        ) : (
          <PreflightResults
            response={response}
            inspectedPlan={inspectedPlan}
            onInspect={handleInspect}
          />
        )}
      </div>

      {/* Inline inspect panel (right column on desktop) */}
      {inspectedPlan && (
        <InspectPanelInline plan={inspectedPlan} onClose={handleCloseInspect} />
      )}
    </div>
  );
};
