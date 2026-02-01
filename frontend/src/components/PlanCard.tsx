/**
 * PlanCard - Display individual multi-load plan with expandable details
 * Desktop-first, inspection-focused UI
 */
import React, { useState } from 'react';
import type { Plan, TimeBlock, FinancialEvent } from '../types/plan';

interface PlanCardProps {
  plan: Plan;
  rank: number; // 1, 2, or 3
  isSelected?: boolean;
  onSelect?: (planId: string) => void;
}

export const PlanCard: React.FC<PlanCardProps> = ({ plan, rank, isSelected = false, onSelect }) => {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  // Calculate summary stats
  const totalWaitingMin = plan.time_blocks
    .filter(b => b.block_type === 'waiting')
    .reduce((sum, b) => sum + b.duration_min, 0);

  const totalDrivingMin = plan.time_blocks
    .filter(b => b.block_type === 'drive_empty' || b.block_type === 'drive_loaded')
    .reduce((sum, b) => sum + b.duration_min, 0);

  const loadChain = plan.loads.map(l => l.load.delivery.city).join(' → ');

  // Risk summary
  const highRisks = plan.risk_signals.filter(r => r.severity === 'high').length;
  const mediumRisks = plan.risk_signals.filter(r => r.severity === 'medium').length;

  return (
    <div
      style={{
        border: isSelected ? '2px solid #3b82f6' : '1px solid #e5e7eb',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '16px',
        backgroundColor: isSelected ? '#eff6ff' : '#ffffff',
      }}
    >
      {/* Header with rank and selection */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              backgroundColor: rank === 1 ? '#10b981' : '#6b7280',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
            }}
          >
            {rank}
          </div>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>
            {plan.loads.length}-Load Plan
          </h3>
        </div>

        {onSelect && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onSelect(plan.plan_id)}
              style={{ width: '18px', height: '18px' }}
            />
            <span style={{ fontSize: '14px' }}>Compare</span>
          </label>
        )}
      </div>

      {/* Top Summary - Always visible */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
        {/* Profit per day - PROMINENT */}
        <div style={{ padding: '16px', backgroundColor: '#f0fdf4', borderRadius: '6px', border: '1px solid #86efac' }}>
          <div style={{ fontSize: '12px', color: '#166534', marginBottom: '4px' }}>Profit per Day</div>
          <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#166534' }}>
            ${plan.profit_per_day_usd.toFixed(0)}
          </div>
        </div>

        {/* Net profit */}
        <div style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Net Profit</div>
          <div style={{ fontSize: '20px', fontWeight: '600' }}>
            ${plan.net_profit_usd.toFixed(0)}
          </div>
        </div>

        {/* Revenue & Costs */}
        <div style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Revenue / Costs</div>
          <div style={{ fontSize: '14px' }}>
            <span style={{ color: '#059669', fontWeight: '600' }}>${plan.total_revenue_usd.toFixed(0)}</span>
            {' / '}
            <span style={{ color: '#dc2626', fontWeight: '600' }}>${plan.total_costs_usd.toFixed(0)}</span>
          </div>
        </div>

        {/* Planning horizon */}
        <div style={{ padding: '16px', backgroundColor: '#f9fafb', borderRadius: '6px', border: '1px solid #e5e7eb' }}>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Horizon</div>
          <div style={{ fontSize: '20px', fontWeight: '600' }}>
            {plan.planning_horizon_days} days
          </div>
        </div>
      </div>

      {/* Load chain and end location */}
      <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: '#fafafa', borderRadius: '4px' }}>
        <div style={{ fontSize: '14px', color: '#374151', marginBottom: '4px' }}>
          <strong>Route:</strong> {loadChain}
        </div>
        <div style={{ fontSize: '14px', color: '#374151' }}>
          <strong>Ends in:</strong> {plan.end_location_name}
        </div>
      </div>

      {/* Risk and confidence badges */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {/* Confidence */}
        <span
          style={{
            padding: '4px 12px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: '500',
            backgroundColor: plan.confidence === 'high' ? '#d1fae5' : plan.confidence === 'medium' ? '#fef3c7' : '#fee2e2',
            color: plan.confidence === 'high' ? '#065f46' : plan.confidence === 'medium' ? '#92400e' : '#991b1b',
          }}
        >
          {plan.confidence.toUpperCase()} confidence
        </span>

        {/* Risk indicators */}
        {highRisks > 0 && (
          <span style={{ padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '500', backgroundColor: '#fee2e2', color: '#991b1b' }}>
            ⚠️ {highRisks} high risk{highRisks > 1 ? 's' : ''}
          </span>
        )}
        {mediumRisks > 0 && (
          <span style={{ padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '500', backgroundColor: '#fef3c7', color: '#92400e' }}>
            {mediumRisks} medium risk{mediumRisks > 1 ? 's' : ''}
          </span>
        )}
        {plan.risk_signals.length === 0 && (
          <span style={{ padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '500', backgroundColor: '#d1fae5', color: '#065f46' }}>
            ✓ Low risk
          </span>
        )}
      </div>

      {/* Expandable Sections */}
      <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
        {/* Timeline Section */}
        <ExpandableSection
          title="Timeline"
          isExpanded={expandedSection === 'timeline'}
          onToggle={() => toggleSection('timeline')}
          badge={`${Math.round(totalDrivingMin / 60)}h drive, ${Math.round(totalWaitingMin / 60)}h wait`}
        >
          <TimelineView blocks={plan.time_blocks} />
        </ExpandableSection>

        {/* Financial Breakdown */}
        <ExpandableSection
          title="Financial Breakdown"
          isExpanded={expandedSection === 'financial'}
          onToggle={() => toggleSection('financial')}
          badge={`${plan.financial_events.length} events`}
        >
          <FinancialBreakdown events={plan.financial_events} plan={plan} />
        </ExpandableSection>

        {/* Explanations */}
        <ExpandableSection
          title="Explanations"
          isExpanded={expandedSection === 'explanations'}
          onToggle={() => toggleSection('explanations')}
          badge={`${plan.explanations.length} reasons`}
        >
          <ExplanationsList explanations={plan.explanations} />
        </ExpandableSection>

        {/* Risks (if any) */}
        {plan.risk_signals.length > 0 && (
          <ExpandableSection
            title="Risk Signals"
            isExpanded={expandedSection === 'risks'}
            onToggle={() => toggleSection('risks')}
            badge={`${plan.risk_signals.length} signal${plan.risk_signals.length > 1 ? 's' : ''}`}
          >
            <RisksList risks={plan.risk_signals} />
          </ExpandableSection>
        )}
      </div>
    </div>
  );
};

// Expandable section component
interface ExpandableSectionProps {
  title: string;
  isExpanded: boolean;
  onToggle: () => void;
  badge?: string;
  children: React.ReactNode;
}

const ExpandableSection: React.FC<ExpandableSectionProps> = ({ title, isExpanded, onToggle, badge, children }) => (
  <div style={{ marginBottom: '12px' }}>
    <button
      onClick={onToggle}
      style={{
        width: '100%',
        padding: '12px',
        backgroundColor: '#f9fafb',
        border: '1px solid #e5e7eb',
        borderRadius: '4px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        cursor: 'pointer',
        fontSize: '14px',
        fontWeight: '600',
      }}
    >
      <span>{title}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {badge && <span style={{ fontSize: '12px', color: '#6b7280', fontWeight: 'normal' }}>{badge}</span>}
        <span>{isExpanded ? '▼' : '▶'}</span>
      </div>
    </button>

    {isExpanded && (
      <div style={{ padding: '16px', border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 4px 4px', backgroundColor: '#ffffff' }}>
        {children}
      </div>
    )}
  </div>
);

// Timeline view
export const TimelineView: React.FC<{ blocks: TimeBlock[] }> = ({ blocks }) => {
  const getBlockColor = (type: string) => {
    switch (type) {
      case 'drive_loaded': return '#3b82f6';
      case 'drive_empty': return '#94a3b8';
      case 'loading': return '#8b5cf6';
      case 'unloading': return '#8b5cf6';
      case 'waiting': return '#f59e0b';
      case 'rest_break': return '#10b981';
      default: return '#6b7280';
    }
  };

  const formatBlockType = (type: string) => {
    return type.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  };

  return (
    <div>
      {blocks.map((block, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '8px 0',
            borderBottom: i < blocks.length - 1 ? '1px solid #f3f4f6' : 'none',
          }}
        >
          <div
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: getBlockColor(block.block_type),
              marginRight: '12px',
            }}
          />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '14px', fontWeight: '500' }}>{formatBlockType(block.block_type)}</div>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>{block.location_name || 'En route'}</div>
          </div>
          <div style={{ fontSize: '12px', color: '#6b7280', textAlign: 'right' }}>
            {Math.round(block.duration_min / 60)}h {block.duration_min % 60}m
          </div>
        </div>
      ))}
    </div>
  );
};

// Financial breakdown
export const FinancialBreakdown: React.FC<{ events: FinancialEvent[]; plan: Plan }> = ({ events, plan }) => {
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);

  return (
    <div>
      {/* Summary */}
      <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: '#f9fafb', borderRadius: '4px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '14px', color: '#059669' }}>Revenue:</span>
          <span style={{ fontSize: '14px', fontWeight: '600', color: '#059669' }}>
            ${plan.total_revenue_usd.toFixed(2)}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '14px', color: '#dc2626' }}>Costs:</span>
          <span style={{ fontSize: '14px', fontWeight: '600', color: '#dc2626' }}>
            -${plan.total_costs_usd.toFixed(2)}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px solid #e5e7eb' }}>
          <span style={{ fontSize: '14px', fontWeight: '600' }}>Net Profit:</span>
          <span style={{ fontSize: '16px', fontWeight: 'bold' }}>
            ${plan.net_profit_usd.toFixed(2)}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
          <span style={{ fontSize: '12px', color: '#6b7280' }}>Per Day:</span>
          <span style={{ fontSize: '14px', fontWeight: '600', color: '#166534' }}>
            ${plan.profit_per_day_usd.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Event list */}
      <div style={{ fontSize: '14px' }}>
        {events.map((event, i) => (
          <div key={i} style={{ marginBottom: '8px' }}>
            <div
              onClick={() => setExpandedEvent(expandedEvent === i ? null : i)}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '8px',
                backgroundColor: '#f9fafb',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: '13px' }}>{event.description}</span>
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: '600',
                  color: event.amount_usd > 0 ? '#059669' : '#dc2626',
                }}
              >
                {event.amount_usd > 0 ? '+' : ''}${event.amount_usd.toFixed(2)}
              </span>
            </div>

            {/* Calculation details (expandable) */}
            {expandedEvent === i && event.calculation_details && (
              <div style={{ padding: '8px', fontSize: '11px', backgroundColor: '#f3f4f6', marginTop: '4px', borderRadius: '4px' }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(event.calculation_details, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// Explanations list
const ExplanationsList: React.FC<{ explanations: string[] }> = ({ explanations }) => (
  <ul style={{ margin: 0, paddingLeft: '20px' }}>
    {explanations.map((exp, i) => (
      <li key={i} style={{ marginBottom: '8px', fontSize: '14px', lineHeight: '1.5' }}>
        {exp}
      </li>
    ))}
  </ul>
);

// Risks list
const RisksList: React.FC<{ risks: any[] }> = ({ risks }) => (
  <div>
    {risks.map((risk, i) => (
      <div
        key={i}
        style={{
          padding: '12px',
          marginBottom: '8px',
          backgroundColor: risk.severity === 'high' ? '#fee2e2' : risk.severity === 'medium' ? '#fef3c7' : '#f3f4f6',
          borderLeft: `4px solid ${risk.severity === 'high' ? '#dc2626' : risk.severity === 'medium' ? '#f59e0b' : '#6b7280'}`,
          borderRadius: '4px',
        }}
      >
        <div style={{ fontSize: '14px', fontWeight: '600', marginBottom: '4px' }}>
          {risk.severity.toUpperCase()} - {risk.risk_type.replace('_', ' ').toUpperCase()}
        </div>
        <div style={{ fontSize: '13px' }}>{risk.description}</div>
        <div style={{ fontSize: '11px', color: '#6b7280', marginTop: '4px' }}>
          Impact: {risk.impact_score}/100
        </div>
      </div>
    ))}
  </div>
);
