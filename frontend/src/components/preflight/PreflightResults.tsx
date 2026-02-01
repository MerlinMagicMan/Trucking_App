import React, { useState } from 'react';
import type { Plan, GeneratePlansResponse } from '../../types/plan';
import { PlanColumn } from './PlanColumn';
import { InspectPanel } from './InspectPanel';

interface PreflightResultsProps {
  response: GeneratePlansResponse | null;
}

export const PreflightResults: React.FC<PreflightResultsProps> = ({ response }) => {
  const [inspectedPlan, setInspectedPlan] = useState<Plan | null>(null);
  const [panelPinned, setPanelPinned] = useState(false);

  const handleInspect = (plan: Plan) => {
    setInspectedPlan(plan);
  };

  const handleClosePanel = () => {
    setInspectedPlan(null);
    setPanelPinned(false);
  };

  if (!response) {
    return (
      <div className="pf-canvas-empty">
        <h2>Ready to plan</h2>
        <p>Set your preferences and click Generate Plans.</p>
      </div>
    );
  }

  if (response.plans.length === 0) {
    return (
      <div className="pf-canvas-empty">
        <h2>No feasible plans found</h2>
        <p>Try adjusting location, horizon, or preferences.</p>
      </div>
    );
  }

  return (
    <>
      {/* Warnings */}
      {response.warnings.length > 0 && (
        <div className="pf-warnings">
          {response.warnings.map((w, i) => (
            <div key={i} className="pf-warning">{w}</div>
          ))}
        </div>
      )}

      {/* Plan columns */}
      <div className="pf-columns">
        {response.plans.map((plan, i) => (
          <PlanColumn
            key={plan.plan_id}
            plan={plan}
            rank={i + 1}
            onInspect={handleInspect}
          />
        ))}
      </div>

      {/* Inspect Panel */}
      <InspectPanel
        plan={inspectedPlan}
        pinned={panelPinned}
        onTogglePin={() => setPanelPinned(!panelPinned)}
        onClose={handleClosePanel}
      />
    </>
  );
};
