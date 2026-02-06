import React, { useState, useEffect, useCallback } from 'react';
import type { Plan, PreflightPreferences, GeneratePlansResponse, GeneratePlansRequest } from '../types/plan';
import { getDataClient } from '../services/dataClient';
import { PreflightSetup } from '../components/preflight/PreflightSetup';
import { PreflightResults } from '../components/preflight/PreflightResults';
import { InspectPanelInline } from '../components/preflight/InspectPanel';
import '../styles/preflight.css';

export const PreflightPage: React.FC = () => {
  const [response, setResponse] = useState<GeneratePlansResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [inspectedPlan, setInspectedPlan] = useState<Plan | null>(null);

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
      setResponse(result);
      setLastUpdated(new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }));
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
        <PreflightResults
          response={response}
          inspectedPlan={inspectedPlan}
          onInspect={handleInspect}
        />
      </div>

      {/* Inline inspect panel (right column on desktop) */}
      {inspectedPlan && (
        <InspectPanelInline plan={inspectedPlan} onClose={handleCloseInspect} />
      )}
    </div>
  );
};
