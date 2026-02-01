import React from 'react';
import type { Plan, TimeBlock } from '../../types/plan';

interface PlanStoryProps {
  plan: Plan;
}

interface DayEntry {
  label: string;
  segments: string[];
}

// Build a lookup: load_id → load info for enriching blocks with miles/dollars
const buildLoadLookup = (plan: Plan) => {
  const map = new Map<string, { route: string; miles: number; revenue: number; deadhead: number }>();
  for (const l of plan.loads) {
    map.set(l.load.id, {
      route: `${l.load.pickup.city} → ${l.load.delivery.city}`,
      miles: l.load.miles || 0,
      revenue: l.revenue_usd,
      deadhead: l.deadhead_miles,
    });
  }
  return map;
};

const narrateBlock = (
  block: TimeBlock,
  loadLookup: Map<string, { route: string; miles: number; revenue: number; deadhead: number }>,
): string | null => {
  const hours = Math.round(block.duration_min / 60);
  const loc = block.location_name || '';
  const loadInfo = block.related_load_id ? loadLookup.get(block.related_load_id) : undefined;

  switch (block.block_type) {
    case 'drive_empty': {
      const dh = loadInfo?.deadhead || (hours * 50);
      return `Deadhead ${dh}mi${loc ? ` to ${loc}` : ''}`;
    }
    case 'loading':
      return `Pickup${loc ? ` ${loc}` : ''}`;
    case 'drive_loaded': {
      const mi = loadInfo?.miles || 0;
      const rev = loadInfo?.revenue || 0;
      const parts = [`Drive ${hours}h`];
      if (mi > 0) parts.push(`${mi}mi`);
      if (loc) parts.push(`to ${loc}`);
      if (rev > 0) parts.push(`$${rev.toFixed(0)}`);
      return parts.join(' · ');
    }
    case 'unloading':
      return `Deliver${loc ? ` ${loc}` : ''}`;
    case 'rest_break':
      return `${hours}h rest`;
    case 'waiting':
      if (block.duration_min > 120) return `Wait ${hours}h`;
      return null;
    case 'available':
      if (block.duration_min > 120) return 'Available for next load';
      return null;
    default:
      return null;
  }
};

const groupByDay = (blocks: TimeBlock[], loadLookup: Map<string, { route: string; miles: number; revenue: number; deadhead: number }>): DayEntry[] => {
  const days: DayEntry[] = [];
  let curDay = '';
  let curSegs: string[] = [];

  for (const block of blocks) {
    const d = new Date(block.start_time);
    const dayLabel = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

    if (dayLabel !== curDay) {
      if (curDay && curSegs.length > 0) days.push({ label: curDay, segments: curSegs });
      curDay = dayLabel;
      curSegs = [];
    }

    const seg = narrateBlock(block, loadLookup);
    if (seg) curSegs.push(seg);
  }

  if (curDay && curSegs.length > 0) days.push({ label: curDay, segments: curSegs });
  return days;
};

export const PlanStory: React.FC<PlanStoryProps> = ({ plan }) => {
  const loadLookup = buildLoadLookup(plan);
  const days = groupByDay(plan.time_blocks, loadLookup);

  if (days.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: '13px' }}>No timeline data.</p>;
  }

  return (
    <div>
      {days.map((day, i) => (
        <div key={i} className="pf-story-day">
          <strong>{day.label}:</strong>{' '}
          {day.segments.map((seg, j) => (
            <span key={j}>
              {j > 0 && <span className="pf-story-arrow"> → </span>}
              {seg.startsWith('Wait') ? (
                <span className="pf-story-wait">{seg}</span>
              ) : (
                seg
              )}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
};
