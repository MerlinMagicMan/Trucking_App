/**
 * ComparePanel (NEXT-002 v1.1)
 *
 * Top-3 plan comparison view for desktop. Shows key metrics + deltas vs #1.
 */

import React from 'react';
import type { Plan } from '../../types/plan';

interface ComparePanelProps {
  plans: Plan[];
  onSelectPlan: (plan: Plan) => void;
}

const rankColors: Record<number, { bg: string; text: string }> = {
  1: { bg: '#fef3c7', text: '#92400e' },
  2: { bg: '#f1f5f9', text: '#475569' },
  3: { bg: '#f1f5f9', text: '#64748b' },
};

function getTotalMiles(plan: Plan): number {
  return plan.loads.reduce((s, l) => s + (l.load.miles || 0) + l.deadhead_miles, 0);
}

function getDeadheadPct(plan: Plan): number {
  let dh = 0;
  let total = 0;
  for (const l of plan.loads) {
    dh += l.deadhead_miles;
    total += (l.load.miles || 0) + l.deadhead_miles;
  }
  return total > 0 ? Math.round((dh / total) * 100) : 0;
}

function getPlanName(plan: Plan): string {
  const cities: string[] = [];
  if (plan.loads.length > 0) {
    cities.push(plan.loads[0].load.pickup.city);
    plan.loads.forEach(l => cities.push(l.load.delivery.city));
  }
  return cities.join(' → ');
}

const DeltaCell: React.FC<{ value: number; unit?: string; higherIsBetter?: boolean }> = ({
  value,
  unit = '',
  higherIsBetter = true,
}) => {
  if (value === 0) return <span style={{ color: '#94a3b8', fontSize: '11px' }}>—</span>;
  const isGood = higherIsBetter ? value > 0 : value < 0;
  const color = isGood ? '#059669' : '#dc2626';
  const prefix = value > 0 ? '+' : '';
  return (
    <span style={{ color, fontSize: '11px', fontWeight: 500 }}>
      {prefix}{value}{unit}
    </span>
  );
};

export const ComparePanel: React.FC<ComparePanelProps> = ({ plans, onSelectPlan }) => {
  const top3 = plans.slice(0, 3);
  if (top3.length === 0) return null;

  const plan1 = top3[0];
  const plan1Miles = getTotalMiles(plan1);
  const plan1Dh = getDeadheadPct(plan1);
  const plan1Score = plan1.ranking_breakdown?.final_score ?? plan1.plan_score;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${top3.length}, 1fr)`,
      gap: '10px',
      marginBottom: '16px',
    }}>
      {top3.map((plan, i) => {
        const rank = i + 1;
        const rc = rankColors[rank] ?? rankColors[3];
        const profit = Math.round(plan.profit_per_day_usd);
        const miles = getTotalMiles(plan);
        const dh = getDeadheadPct(plan);
        const score = plan.ranking_breakdown?.final_score ?? plan.plan_score;

        const milesDelta = miles - plan1Miles;
        const dhDelta = dh - plan1Dh;
        const scoreDelta = score - plan1Score;

        return (
          <div
            key={plan.plan_id}
            onClick={() => onSelectPlan(plan)}
            style={{
              background: '#fff',
              border: rank === 1 ? '2px solid #059669' : '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '12px',
              cursor: 'pointer',
              transition: 'border-color 0.15s',
            }}
          >
            {/* Rank + Profit */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                width: '22px', height: '22px', borderRadius: '50%',
                fontSize: '11px', fontWeight: 700,
                background: rc.bg, color: rc.text,
              }}>
                {rank}
              </span>
              <span style={{ fontSize: '20px', fontWeight: 700, color: '#059669' }}>
                ${profit}
              </span>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>/day</span>
            </div>

            {/* Route */}
            <div style={{
              fontSize: '12px', fontWeight: 500, color: '#0f172a',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              marginBottom: '8px', paddingBottom: '8px', borderBottom: '1px solid #e2e8f0',
            }}>
              {getPlanName(plan)}
            </div>

            {/* Explanation */}
            {plan.ranking_explanation && (
              <div style={{
                fontSize: '12px', color: '#475569', fontStyle: 'italic',
                marginBottom: '8px', lineHeight: 1.3,
              }}>
                {plan.ranking_explanation}
              </div>
            )}

            {/* Metrics table */}
            <div style={{ fontSize: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                <span style={{ color: '#64748b' }}>Miles</span>
                <span style={{ fontWeight: 500 }}>
                  {miles.toLocaleString()}
                  {rank > 1 && <> <DeltaCell value={milesDelta} /></>}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                <span style={{ color: '#64748b' }}>Deadhead</span>
                <span style={{ fontWeight: 500 }}>
                  {dh}%
                  {rank > 1 && <> <DeltaCell value={dhDelta} unit="%" higherIsBetter={false} /></>}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                <span style={{ color: '#64748b' }}>Confidence</span>
                <span style={{ fontWeight: 500 }}>{plan.confidence}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                <span style={{ color: '#64748b' }}>Score</span>
                <span style={{ fontWeight: 600 }}>
                  {score}
                  {rank > 1 && <> <DeltaCell value={scoreDelta} /></>}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
