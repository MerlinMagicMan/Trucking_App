/**
 * PlansPage - Multi-load plan generation and inspection
 * Desktop-first layout for plan comparison and analysis
 */
import React, { useState } from 'react';
import { PlanCard } from '../components/PlanCard';
import { generatePlans } from '../services/api';
import type { GeneratePlansRequest, GeneratePlansResponse, Plan } from '../types/plan';

export const PlansPage: React.FC = () => {
  // Form state
  const [latitude, setLatitude] = useState<string>('35.4676'); // Oklahoma City default
  const [longitude, setLongitude] = useState<string>('-97.5164');
  const [driveRemaining, setDriveRemaining] = useState<string>('660'); // 11 hours
  const [onDutyRemaining, setOnDutyRemaining] = useState<string>('840'); // 14 hours
  const [cycleRemaining, setCycleRemaining] = useState<string>('4200'); // 70 hours
  const [planningHorizon, setPlanningHorizon] = useState<string>('7');
  const [maxPlans, setMaxPlans] = useState<string>('3');
  const [radiusMiles, setRadiusMiles] = useState<string>('250');

  // Response state
  const [response, setResponse] = useState<GeneratePlansResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Comparison state
  const [selectedPlans, setSelectedPlans] = useState<Set<string>>(new Set());

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const request: GeneratePlansRequest = {
        current_lat: parseFloat(latitude),
        current_lng: parseFloat(longitude),
        hos: {
          drive_remaining_min: parseInt(driveRemaining),
          on_duty_remaining_min: parseInt(onDutyRemaining),
          cycle_remaining_min: parseInt(cycleRemaining),
        },
        planning_horizon_days: parseInt(planningHorizon),
        max_plans: parseInt(maxPlans),
        radius_miles: parseInt(radiusMiles),
      };

      const result = await generatePlans(request);
      setResponse(result);
      setSelectedPlans(new Set()); // Reset selection
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate plans');
    } finally {
      setLoading(false);
    }
  };

  const togglePlanSelection = (planId: string) => {
    const newSelection = new Set(selectedPlans);
    if (newSelection.has(planId)) {
      newSelection.delete(planId);
    } else {
      // Only allow 2 plans for comparison
      if (newSelection.size < 2) {
        newSelection.add(planId);
      }
    }
    setSelectedPlans(newSelection);
  };

  // Get selected plans for comparison
  const plansToCompare: Plan[] = response?.plans.filter(p => selectedPlans.has(p.plan_id)) || [];

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '20px' }}>
      <h1 style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
        Multi-Load Plan Generator
      </h1>
      <p style={{ color: '#6b7280', marginBottom: '32px' }}>
        Generate 0–3 strategically different multi-day plans. Plans, not loads, are the unit of decision.
      </p>

      {/* Input Form */}
      <div style={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', marginBottom: '24px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '20px' }}>Truck Snapshot & Parameters</h2>

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px' }}>
            {/* Location */}
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                Latitude
              </label>
              <input
                type="number"
                step="0.0001"
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                required
                min="-90"
                max="90"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                Longitude
              </label>
              <input
                type="number"
                step="0.0001"
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                required
                min="-180"
                max="180"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
            </div>

            {/* HOS */}
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                Drive Remaining (min)
              </label>
              <input
                type="number"
                value={driveRemaining}
                onChange={(e) => setDriveRemaining(e.target.value)}
                required
                min="0"
                max="660"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
              <span style={{ fontSize: '12px', color: '#6b7280' }}>Max 660 (11 hours)</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                On-Duty Remaining (min)
              </label>
              <input
                type="number"
                value={onDutyRemaining}
                onChange={(e) => setOnDutyRemaining(e.target.value)}
                required
                min="0"
                max="840"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
              <span style={{ fontSize: '12px', color: '#6b7280' }}>Max 840 (14 hours)</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                Cycle Remaining (min)
              </label>
              <input
                type="number"
                value={cycleRemaining}
                onChange={(e) => setCycleRemaining(e.target.value)}
                required
                min="0"
                max="4200"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
              <span style={{ fontSize: '12px', color: '#6b7280' }}>Max 4200 (70 hours)</span>
            </div>

            {/* Plan parameters */}
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                Planning Horizon (days)
              </label>
              <input
                type="number"
                value={planningHorizon}
                onChange={(e) => setPlanningHorizon(e.target.value)}
                required
                min="7"
                max="14"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
              <span style={{ fontSize: '12px', color: '#6b7280' }}>7-14 days</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                Max Plans
              </label>
              <input
                type="number"
                value={maxPlans}
                onChange={(e) => setMaxPlans(e.target.value)}
                required
                min="1"
                max="3"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
              <span style={{ fontSize: '12px', color: '#6b7280' }}>1-3 plans</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
                Search Radius (miles)
              </label>
              <input
                type="number"
                value={radiusMiles}
                onChange={(e) => setRadiusMiles(e.target.value)}
                required
                min="50"
                max="1000"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                }}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: '24px',
              padding: '12px 32px',
              backgroundColor: loading ? '#9ca3af' : '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '16px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Generating Plans...' : 'Generate Plans'}
          </button>
        </form>
      </div>

      {/* Error Display */}
      {error && (
        <div style={{ backgroundColor: '#fee2e2', border: '1px solid #fca5a5', borderRadius: '8px', padding: '16px', marginBottom: '24px' }}>
          <div style={{ fontWeight: '600', color: '#991b1b', marginBottom: '4px' }}>Error</div>
          <div style={{ color: '#7f1d1d' }}>{error}</div>
        </div>
      )}

      {/* Warnings Display */}
      {response && response.warnings.length > 0 && (
        <div style={{ backgroundColor: '#fef3c7', border: '1px solid #fbbf24', borderRadius: '8px', padding: '16px', marginBottom: '24px' }}>
          <div style={{ fontWeight: '600', color: '#92400e', marginBottom: '8px' }}>Warnings</div>
          <ul style={{ margin: 0, paddingLeft: '20px' }}>
            {response.warnings.map((warning, i) => (
              <li key={i} style={{ color: '#78350f' }}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* No Plans Case */}
      {response && response.plans.length === 0 && (
        <div style={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '48px', textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📭</div>
          <h3 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '8px' }}>No Feasible Plans Found</h3>
          <p style={{ color: '#6b7280', marginBottom: '16px' }}>
            No multi-load plans could be generated for the current parameters.
          </p>
          <p style={{ fontSize: '14px', color: '#374151' }}>
            Try:
          </p>
          <ul style={{ textAlign: 'left', maxWidth: '400px', margin: '8px auto', color: '#374151', fontSize: '14px' }}>
            <li>Increasing search radius</li>
            <li>Checking HOS limits (enough drive time?)</li>
            <li>Adjusting planning horizon</li>
          </ul>
        </div>
      )}

      {/* Plans Display */}
      {response && response.plans.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: '600' }}>
              {response.plans.length} Plan{response.plans.length > 1 ? 's' : ''} Generated
            </h2>
            {response.plans.length > 0 && (
              <div style={{ fontSize: '14px', color: '#6b7280' }}>
                {response.plans[0].loads_analyzed} loads analyzed
              </div>
            )}
          </div>

          {/* Plans */}
          {response.plans.map((plan, i) => (
            <PlanCard
              key={plan.plan_id}
              plan={plan}
              rank={i + 1}
              isSelected={selectedPlans.has(plan.plan_id)}
              onSelect={togglePlanSelection}
            />
          ))}

          {/* Comparison Strip */}
          {plansToCompare.length === 2 && (
            <div style={{ position: 'sticky', bottom: '20px', backgroundColor: '#ffffff', border: '2px solid #3b82f6', borderRadius: '8px', padding: '20px', marginTop: '20px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '16px' }}>Plan Comparison</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                {/* Profit per day delta */}
                <div>
                  <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Profit Per Day Delta</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                    ${(plansToCompare[0].profit_per_day_usd - plansToCompare[1].profit_per_day_usd).toFixed(0)}
                  </div>
                  <div style={{ fontSize: '12px', color: '#6b7280' }}>
                    Plan 1: ${plansToCompare[0].profit_per_day_usd.toFixed(0)} vs Plan 2: ${plansToCompare[1].profit_per_day_usd.toFixed(0)}
                  </div>
                </div>

                {/* Waiting time delta */}
                <div>
                  <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Waiting Time Delta</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                    {(() => {
                      const wait1 = plansToCompare[0].time_blocks.filter(b => b.block_type === 'waiting').reduce((s, b) => s + b.duration_min, 0);
                      const wait2 = plansToCompare[1].time_blocks.filter(b => b.block_type === 'waiting').reduce((s, b) => s + b.duration_min, 0);
                      return `${Math.round((wait1 - wait2) / 60)}h`;
                    })()}
                  </div>
                </div>

                {/* Risk differences */}
                <div>
                  <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Risk Signals</div>
                  <div style={{ fontSize: '14px' }}>
                    Plan 1: {plansToCompare[0].risk_signals.length} vs Plan 2: {plansToCompare[1].risk_signals.length}
                  </div>
                </div>

                {/* End locations */}
                <div>
                  <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>End Locations</div>
                  <div style={{ fontSize: '14px' }}>
                    {plansToCompare[0].end_location_name === plansToCompare[1].end_location_name
                      ? `Both end in ${plansToCompare[0].end_location_name}`
                      : `Plan 1: ${plansToCompare[0].end_location_name} vs Plan 2: ${plansToCompare[1].end_location_name}`}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
