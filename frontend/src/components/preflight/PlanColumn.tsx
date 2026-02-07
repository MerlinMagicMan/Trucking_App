import React from 'react';
import type { Plan } from '../../types/plan';

interface PlanColumnProps {
  plan: Plan;
  rank: number;
  onInspect: (plan: Plan) => void;
  isSelected?: boolean;
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

// Generate plan name from route: "OKC → Dallas → ATL"
const getPlanName = (plan: Plan): string => {
  const cities: string[] = [];
  if (plan.loads.length > 0) {
    cities.push(plan.loads[0].load.pickup.city);
    plan.loads.forEach(l => cities.push(l.load.delivery.city));
  }
  return cities.join(' → ');
};

export const PlanColumn: React.FC<PlanColumnProps> = ({ plan, rank, onInspect, isSelected }) => {
  const risk = getRiskLevel(plan);
  const miles = getTotalMiles(plan);
  const rate = getAvgRate(plan);
  const wait = getWaitHours(plan);

  return (
    <div
      className={`pf-column ${isSelected ? 'pf-column-selected' : ''}`}
      onClick={() => onInspect(plan)}
    >
      {/* Header: rank + profit hero inline */}
      <div className="pf-plan-header">
        <span className={`pf-rank ${rank === 1 ? 'pf-rank-1' : 'pf-rank-other'}`}>{rank}</span>
        <div className="pf-header-profit">
          <span className="pf-profit-hero">${plan.profit_per_day_usd.toFixed(0)}</span>
          <span className="pf-profit-label">/day</span>
        </div>
      </div>

      {/* Route name */}
      <div className="pf-plan-route">{getPlanName(plan)}</div>

      {/* Ranking explanation (NEXT-002) */}
      {plan.ranking_explanation && (
        <div className="pf-ranking-explanation">{plan.ranking_explanation}</div>
      )}

      {/* Compact metrics grid */}
      <div className="pf-metrics-compact">
        <div className="pf-mc"><span className="l">Net</span><span className="v">${plan.net_profit_usd.toFixed(0)}</span></div>
        <div className="pf-mc"><span className="l">$/mi</span><span className="v">${rate.toFixed(2)}</span></div>
        <div className="pf-mc"><span className="l">Mi</span><span className="v">{miles.toLocaleString()}</span></div>
        <div className="pf-mc"><span className="l">Wait</span><span className="v">{wait}h</span></div>
      </div>

      {/* Badges + End location */}
      <div className="pf-plan-footer">
        <div className="pf-badges">
          <span className={`pf-badge pf-badge-${risk}`}>{risk}</span>
          <span className={`pf-badge pf-badge-${plan.confidence}`}>{plan.confidence}</span>
        </div>
        <span className="pf-end-location">→ {plan.end_location_name}</span>
      </div>
    </div>
  );
};
