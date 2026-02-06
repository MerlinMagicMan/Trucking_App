/**
 * Demo Plan Generator (DEMO-001)
 *
 * Generates deterministic multi-load plans from demo routes.
 * Used by demoClient.generatePlans() when demo mode is active.
 */

import type { RouteRecord } from '../types/org';
import type {
  GeneratePlansRequest,
  GeneratePlansResponse,
  Plan,
  LoadInPlan,
  CanonicalLoad,
  TimeBlock,
  FinancialEvent,
  Confidence,
  HOSSnapshot,
} from '../types/plan';

// Seeded random for determinism
function seededRandom(seed: number): () => number {
  return () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
}

function createSeedFromRequest(request: GeneratePlansRequest): number {
  // Deterministic seed from request parameters
  return Math.floor(
    (request.current_lat * 1000 + request.current_lng * 100 + (request.planning_horizon_days || 7)) % 10000
  );
}

export function generateDemoPlans(
  request: GeneratePlansRequest,
  routes: RouteRecord[]
): GeneratePlansResponse {
  const seed = createSeedFromRequest(request);
  const random = seededRandom(seed);
  const timestamp = new Date().toISOString();
  const snapshotId = `demo-snapshot-${Date.now()}`;

  const horizonDays = request.planning_horizon_days || 7;
  const maxPlans = Math.min(request.max_plans || 3, 5);

  // Need at least 1 route to generate plans
  if (routes.length === 0) {
    return {
      snapshot_id: snapshotId,
      plans: [],
      warnings: ['No routes available in demo mode. Seed routes first via Admin Console.'],
      metadata: {
        planning_horizon_days: horizonDays,
        radius_miles: request.radius_miles || 250,
        plans_requested: maxPlans,
        plans_generated: 0,
      },
    };
  }

  const plans: Plan[] = [];
  const planCount = Math.min(maxPlans, Math.max(3, Math.min(5, routes.length)));

  for (let i = 0; i < planCount; i++) {
    const plan = generateSinglePlan(
      i + 1,
      request,
      routes,
      horizonDays,
      random,
      timestamp
    );
    plans.push(plan);
  }

  // Sort by profit_per_day descending
  plans.sort((a, b) => b.profit_per_day_usd - a.profit_per_day_usd);

  return {
    snapshot_id: snapshotId,
    plans,
    warnings: [],
    metadata: {
      planning_horizon_days: horizonDays,
      radius_miles: request.radius_miles || 250,
      plans_requested: maxPlans,
      plans_generated: plans.length,
    },
  };
}

function generateSinglePlan(
  index: number,
  request: GeneratePlansRequest,
  routes: RouteRecord[],
  horizonDays: number,
  random: () => number,
  timestamp: string
): Plan {
  // Deterministic selection of loads for this plan
  const loadsPerPlan = Math.min(1 + Math.floor(random() * 3), Math.min(3, routes.length));
  const shuffledRoutes = [...routes].sort(() => random() - 0.5);
  const selectedRoutes = shuffledRoutes.slice(index * loadsPerPlan % routes.length, (index * loadsPerPlan % routes.length) + loadsPerPlan);

  // If we wrapped around, pick from start
  if (selectedRoutes.length < loadsPerPlan) {
    const remaining = loadsPerPlan - selectedRoutes.length;
    selectedRoutes.push(...shuffledRoutes.slice(0, remaining));
  }

  const loads: LoadInPlan[] = selectedRoutes.map((route, seq) =>
    routeToLoadInPlan(route, seq + 1, random)
  );

  // Calculate financials
  const totalRevenue = loads.reduce((sum, l) => sum + l.revenue_usd, 0);
  const totalMiles = loads.reduce((sum, l) => sum + (l.load.miles || 300), 0);
  const totalDeadhead = loads.reduce((sum, l) => sum + l.deadhead_miles, 0);

  const fuelCost = (totalMiles + totalDeadhead) * 0.62;
  const tolls = totalRevenue * 0.04;
  const maintenance = totalRevenue * 0.02;
  const totalCosts = fuelCost + tolls + maintenance;
  const netProfit = totalRevenue - totalCosts;
  const profitPerDay = netProfit / horizonDays;

  // Confidence based on load count
  let confidence: Confidence;
  let confidenceScore: number;
  if (loads.length >= 3) {
    confidence = 'high';
    confidenceScore = 85;
  } else if (loads.length === 2) {
    confidence = 'medium';
    confidenceScore = 65;
  } else {
    confidence = 'low';
    confidenceScore = 45;
  }

  // Plan score (0-100) based on profitability
  const planScore = Math.min(100, Math.max(0, Math.round(50 + profitPerDay / 10)));

  const lastLoad = loads[loads.length - 1];
  const endLocation = lastLoad?.load.delivery;

  return {
    plan_id: `demo-plan-${String(index).padStart(3, '0')}`,
    created_at: timestamp,
    truck_snapshot: {
      snapshot_id: `demo-snapshot-${index}`,
      timestamp,
      current_lat: request.current_lat,
      current_lng: request.current_lng,
      hos: request.hos,
    },
    planning_horizon_days: horizonDays,
    loads,
    time_blocks: generateTimeBlocks(loads, request.hos),
    end_location_lat: endLocation?.lat || request.current_lat,
    end_location_lng: endLocation?.lng || request.current_lng,
    end_location_name: endLocation ? `${endLocation.city}, ${endLocation.state}` : 'Starting Location',
    total_revenue_usd: Math.round(totalRevenue * 100) / 100,
    total_costs_usd: Math.round(totalCosts * 100) / 100,
    net_profit_usd: Math.round(netProfit * 100) / 100,
    profit_per_day_usd: Math.round(profitPerDay * 100) / 100,
    financial_events: generateFinancialEvents(loads, fuelCost, tolls, maintenance),
    risk_signals: [],
    maintenance_events: [],
    plan_score: planScore,
    confidence,
    confidence_score: confidenceScore,
    explanations: generateExplanations(loads, profitPerDay, confidence),
    warnings: [],
    loads_analyzed: routes.length,
    plans_generated: 1,
  };
}

function routeToLoadInPlan(route: RouteRecord, sequence: number, random: () => number): LoadInPlan {
  const deadheadMiles = Math.round(20 + random() * 80);
  const miles = route.miles || 300;
  const rate = route.rate_total;

  const fuelCost = (miles + deadheadMiles) * 0.62;
  const tollCost = rate * 0.04;
  const netRevenue = rate - fuelCost - tollCost;

  const canonicalLoad: CanonicalLoad = {
    id: `demo-load-${route.id}`,
    source: route.source,
    external_id: route.external_id || route.id,
    posted_at: route.posted_at || route.created_at,
    equipment: 'reefer',
    pickup: {
      city: route.pickup_city,
      state: route.pickup_state,
      lat: 32.7767 + random() * 2,
      lng: -96.7970 + random() * 2,
    },
    delivery: {
      city: route.delivery_city,
      state: route.delivery_state,
      lat: 32.7767 + random() * 2,
      lng: -96.7970 + random() * 2,
    },
    rate_total: rate,
    miles: miles,
  };

  return {
    load: canonicalLoad,
    sequence_number: sequence,
    deadhead_miles: deadheadMiles,
    revenue_usd: rate,
    estimated_fuel_cost_usd: fuelCost,
    estimated_toll_cost_usd: tollCost,
    net_revenue_usd: netRevenue,
    time_blocks: [],
  };
}

function generateTimeBlocks(loads: LoadInPlan[], _hos: HOSSnapshot): TimeBlock[] {
  const blocks: TimeBlock[] = [];
  const now = new Date();
  let currentTime = now;

  for (const load of loads) {
    // Drive empty to pickup
    const driveEmptyDuration = Math.round(load.deadhead_miles / 50 * 60);
    blocks.push({
      start_time: currentTime.toISOString(),
      end_time: new Date(currentTime.getTime() + driveEmptyDuration * 60000).toISOString(),
      duration_min: driveEmptyDuration,
      block_type: 'drive_empty',
      location_name: `En route to ${load.load.pickup.city}`,
    });
    currentTime = new Date(currentTime.getTime() + driveEmptyDuration * 60000);

    // Loading
    blocks.push({
      start_time: currentTime.toISOString(),
      end_time: new Date(currentTime.getTime() + 60 * 60000).toISOString(),
      duration_min: 60,
      block_type: 'loading',
      location_name: `${load.load.pickup.city}, ${load.load.pickup.state}`,
      related_load_id: load.load.id,
    });
    currentTime = new Date(currentTime.getTime() + 60 * 60000);

    // Drive loaded
    const driveDuration = Math.round((load.load.miles || 300) / 55 * 60);
    blocks.push({
      start_time: currentTime.toISOString(),
      end_time: new Date(currentTime.getTime() + driveDuration * 60000).toISOString(),
      duration_min: driveDuration,
      block_type: 'drive_loaded',
      location_name: `En route to ${load.load.delivery.city}`,
      related_load_id: load.load.id,
    });
    currentTime = new Date(currentTime.getTime() + driveDuration * 60000);

    // Unloading
    blocks.push({
      start_time: currentTime.toISOString(),
      end_time: new Date(currentTime.getTime() + 45 * 60000).toISOString(),
      duration_min: 45,
      block_type: 'unloading',
      location_name: `${load.load.delivery.city}, ${load.load.delivery.state}`,
      related_load_id: load.load.id,
    });
    currentTime = new Date(currentTime.getTime() + 45 * 60000);
  }

  return blocks;
}

function generateFinancialEvents(
  loads: LoadInPlan[],
  fuelCost: number,
  tolls: number,
  maintenance: number
): FinancialEvent[] {
  const events: FinancialEvent[] = [];
  const now = new Date().toISOString();

  for (const load of loads) {
    events.push({
      timestamp: now,
      event_type: 'revenue',
      amount_usd: load.revenue_usd,
      description: `Load revenue: ${load.load.pickup.city} → ${load.load.delivery.city}`,
      related_load_id: load.load.id,
    });
  }

  events.push({
    timestamp: now,
    event_type: 'fuel_cost',
    amount_usd: -fuelCost,
    description: 'Estimated fuel cost',
  });

  events.push({
    timestamp: now,
    event_type: 'toll_cost',
    amount_usd: -tolls,
    description: 'Estimated tolls',
  });

  events.push({
    timestamp: now,
    event_type: 'maintenance_reserve',
    amount_usd: -maintenance,
    description: 'Maintenance reserve',
  });

  return events;
}

function generateExplanations(loads: LoadInPlan[], profitPerDay: number, confidence: Confidence): string[] {
  const explanations: string[] = [];

  explanations.push(
    `Plan includes ${loads.length} load${loads.length > 1 ? 's' : ''} with projected profit of $${profitPerDay.toFixed(0)}/day.`
  );

  if (loads.length > 0) {
    const firstLoad = loads[0];
    explanations.push(
      `Primary route: ${firstLoad.load.pickup.city}, ${firstLoad.load.pickup.state} → ${firstLoad.load.delivery.city}, ${firstLoad.load.delivery.state}.`
    );
  }

  if (confidence === 'high') {
    explanations.push('High confidence based on strong lane data and realistic load combinations.');
  } else if (confidence === 'medium') {
    explanations.push('Medium confidence — consider market conditions before committing.');
  } else {
    explanations.push('Lower confidence due to limited data. Additional routes recommended.');
  }

  return explanations;
}
