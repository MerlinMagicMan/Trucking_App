import React from 'react';
import type { Plan } from '../../types/plan';
import { PlanStory } from './PlanStory';

interface PlanColumnProps {
  plan: Plan;
  rank: number;
  onInspect: (plan: Plan) => void;
}

const getRiskLevel = (plan: Plan): 'low' | 'medium' | 'high' => {
  if (plan.risk_signals.filter(r => r.severity === 'high').length > 0) return 'high';
  if (plan.risk_signals.filter(r => r.severity === 'medium').length > 1) return 'medium';
  return 'low';
};

const getTotalMiles = (plan: Plan): number =>
  plan.loads.reduce((s, l) => s + (l.load.miles || 0) + l.deadhead_miles, 0);

const getAvgRate = (plan: Plan): number => {
  const m = getTotalMiles(plan);
  return m > 0 ? plan.total_revenue_usd / m : 0;
};

const getWaitHours = (plan: Plan): number =>
  Math.round(plan.time_blocks.filter(b => b.block_type === 'waiting').reduce((s, b) => s + b.duration_min, 0) / 60);

const getMaintenanceImpact = (miles: number): string =>
  miles > 3000 ? 'High' : miles > 1500 ? 'Medium' : 'Low';

const getKeyRisk = (plan: Plan): string => {
  const r = plan.risk_signals.find(r => r.severity === 'high') || plan.risk_signals.find(r => r.severity === 'medium');
  if (!r) return 'None';
  return r.description.length > 40 ? r.description.slice(0, 40) + '...' : r.description;
};

const maintenanceBadge = (impact: string) =>
  impact === 'High' ? 'pf-badge-high' : impact === 'Medium' ? 'pf-badge-medium' : 'pf-badge-low';

// Generate plan name from route: "OKC → Dallas → ATL"
const getPlanName = (plan: Plan): string => {
  const cities: string[] = [];
  if (plan.loads.length > 0) {
    cities.push(plan.loads[0].load.pickup.city);
    plan.loads.forEach(l => cities.push(l.load.delivery.city));
  }
  return cities.join(' → ');
};

export const PlanColumn: React.FC<PlanColumnProps> = ({ plan, rank, onInspect }) => {
  const risk = getRiskLevel(plan);
  const miles = getTotalMiles(plan);
  const rate = getAvgRate(plan);
  const wait = getWaitHours(plan);
  const maint = getMaintenanceImpact(miles);

  return (
    <div className="pf-column">
      {/* Header: rank + route name */}
      <div className="pf-plan-header">
        <span className={`pf-rank ${rank === 1 ? 'pf-rank-1' : 'pf-rank-other'}`}>{rank}</span>
        <span className="pf-plan-name">{getPlanName(plan)}</span>
      </div>

      {/* Profit hero */}
      <div className="pf-profit-section">
        <div className="pf-profit-label">Profit / Day</div>
        <div className="pf-profit-hero">${plan.profit_per_day_usd.toFixed(0)}</div>
        <div className="pf-profit-sub">${plan.net_profit_usd.toFixed(0)} net over {plan.planning_horizon_days}d</div>
      </div>

      {/* Metrics: inline row */}
      <div className="pf-metrics-row">
        <div className="pf-metric-inline"><span className="label">$/mi</span> <span className="value">${rate.toFixed(2)}</span></div>
        <div className="pf-metric-inline"><span className="label">Miles</span> <span className="value">{miles.toLocaleString()}</span></div>
        <div className="pf-metric-inline"><span className="label">Rev</span> <span className="value">${plan.total_revenue_usd.toFixed(0)}</span></div>
        <div className="pf-metric-inline"><span className="label">Ends</span> <span className="value">{plan.end_location_name}</span></div>
      </div>

      {/* Badges */}
      <div className="pf-badges">
        <span className={`pf-badge pf-badge-${risk}`}>{risk} risk</span>
        <span className={`pf-badge ${maintenanceBadge(maint)}`}>{maint} maint</span>
      </div>

      {/* Story */}
      <div className="pf-story">
        <h3>Week</h3>
        <PlanStory plan={plan} />
      </div>

      {/* Tradeoffs: single dense row */}
      <div className="pf-tradeoffs">
        <div className="pf-tradeoff-item"><span className="pf-tradeoff-label">Wait</span> <span className="pf-tradeoff-value">{wait}h</span></div>
        <div className="pf-tradeoff-item"><span className="pf-tradeoff-label">Mi</span> <span className="pf-tradeoff-value">{miles.toLocaleString()}</span></div>
        <div className="pf-tradeoff-item"><span className="pf-tradeoff-label">$/mi</span> <span className="pf-tradeoff-value">${rate.toFixed(2)}</span></div>
        <div className="pf-tradeoff-item"><span className="pf-tradeoff-label">Risk</span> <span className="pf-tradeoff-value">{getKeyRisk(plan)}</span></div>
      </div>

      <button className="pf-inspect-btn" onClick={() => onInspect(plan)} type="button">Inspect →</button>
    </div>
  );
};
