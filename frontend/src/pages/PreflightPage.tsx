import React, { useState } from 'react';
import type { PreflightPreferences, GeneratePlansResponse, GeneratePlansRequest } from '../types/plan';
import { generatePlans } from '../services/api';
import { PreflightSetup } from '../components/preflight/PreflightSetup';
import { PreflightResults } from '../components/preflight/PreflightResults';
import '../styles/preflight.css';

export const PreflightPage: React.FC = () => {
  const [response, setResponse] = useState<GeneratePlansResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

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

      const result = await generatePlans(request);
      setResponse(result);
      setLastUpdated(new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }));
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

  return (
    <div className="pf-workspace">
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
        <PreflightResults response={response} />
      </div>
    </div>
  );
};
