/**
 * Deterministic Seed Data Generator (DEMO-001)
 *
 * Provides functions to seed demo data and reset storage.
 * All generated data is deterministic (same output every time).
 */

import type { Org, Truck, RouteRecord, PlanHistoryItem } from '../types/org';
import { setActiveOrgId, setActiveTruckId } from './orgContext';

// ---- Storage Keys (must match demoClient) ----

const KEYS = {
  config: 'demo_v1_config',
  orgs: 'demo_v1_orgs',
  trucks: 'demo_v1_trucks',
  routes: 'demo_v1_routes',
  planHistory: 'demo_v1_plan_history',
};

// ---- Seed Functions ----

export function seedDemoOrg(): Org {
  const org: Org = {
    id: 'demo-org-001',
    name: 'Demo Fleet Inc',
    tier: 'premium',
    created_at: '2026-01-01T00:00:00Z',
  };

  const orgs = [org];
  localStorage.setItem(KEYS.orgs, JSON.stringify(orgs));
  setActiveOrgId(org.id);

  return org;
}

export function seedDemoTruck(): Truck {
  const truck: Truck = {
    id: 'demo-truck-001',
    org_id: 'demo-org-001',
    name: 'Truck Alpha',
    equipment_type: 'reefer',
    home_base_city: 'Dallas',
    home_base_state: 'TX',
    created_at: '2026-01-15T00:00:00Z',
  };

  const existing = JSON.parse(localStorage.getItem(KEYS.trucks) || '[]');
  // Avoid duplicates
  const filtered = existing.filter((t: Truck) => t.id !== truck.id);
  filtered.push(truck);
  localStorage.setItem(KEYS.trucks, JSON.stringify(filtered));
  setActiveTruckId(truck.id);

  return truck;
}

export function seedDemoRoutes(): RouteRecord[] {
  const orgId = 'demo-org-001';

  // Texas triangle + regional routes
  const routeData: Array<{
    pickup_city: string;
    pickup_state: string;
    delivery_city: string;
    delivery_state: string;
    miles: number;
    rate: number;
  }> = [
    // Texas internal
    { pickup_city: 'Dallas', pickup_state: 'TX', delivery_city: 'Houston', delivery_state: 'TX', miles: 240, rate: 520 },
    { pickup_city: 'Houston', pickup_state: 'TX', delivery_city: 'San Antonio', delivery_state: 'TX', miles: 200, rate: 440 },
    { pickup_city: 'San Antonio', pickup_state: 'TX', delivery_city: 'Austin', delivery_state: 'TX', miles: 80, rate: 200 },
    { pickup_city: 'Austin', pickup_state: 'TX', delivery_city: 'Dallas', delivery_state: 'TX', miles: 195, rate: 430 },
    { pickup_city: 'Dallas', pickup_state: 'TX', delivery_city: 'El Paso', delivery_state: 'TX', miles: 635, rate: 1400 },

    // Texas to Oklahoma
    { pickup_city: 'Dallas', pickup_state: 'TX', delivery_city: 'Oklahoma City', delivery_state: 'OK', miles: 210, rate: 480 },
    { pickup_city: 'Houston', pickup_state: 'TX', delivery_city: 'Tulsa', delivery_state: 'OK', miles: 480, rate: 1050 },
    { pickup_city: 'Oklahoma City', pickup_state: 'OK', delivery_city: 'Dallas', delivery_state: 'TX', miles: 210, rate: 460 },
    { pickup_city: 'Tulsa', pickup_state: 'OK', delivery_city: 'Houston', delivery_state: 'TX', miles: 480, rate: 1020 },

    // Texas to Arkansas
    { pickup_city: 'Dallas', pickup_state: 'TX', delivery_city: 'Little Rock', delivery_state: 'AR', miles: 320, rate: 720 },
    { pickup_city: 'Little Rock', pickup_state: 'AR', delivery_city: 'Dallas', delivery_state: 'TX', miles: 320, rate: 700 },
    { pickup_city: 'Houston', pickup_state: 'TX', delivery_city: 'Little Rock', delivery_state: 'AR', miles: 450, rate: 980 },

    // Texas to Louisiana
    { pickup_city: 'Houston', pickup_state: 'TX', delivery_city: 'New Orleans', delivery_state: 'LA', miles: 350, rate: 780 },
    { pickup_city: 'New Orleans', pickup_state: 'LA', delivery_city: 'Houston', delivery_state: 'TX', miles: 350, rate: 750 },
    { pickup_city: 'Dallas', pickup_state: 'TX', delivery_city: 'Shreveport', delivery_state: 'LA', miles: 190, rate: 420 },
    { pickup_city: 'Shreveport', pickup_state: 'LA', delivery_city: 'Dallas', delivery_state: 'TX', miles: 190, rate: 400 },

    // Cross-regional
    { pickup_city: 'Oklahoma City', pickup_state: 'OK', delivery_city: 'New Orleans', delivery_state: 'LA', miles: 680, rate: 1500 },
    { pickup_city: 'Little Rock', pickup_state: 'AR', delivery_city: 'Houston', delivery_state: 'TX', miles: 450, rate: 950 },
    { pickup_city: 'El Paso', pickup_state: 'TX', delivery_city: 'Dallas', delivery_state: 'TX', miles: 635, rate: 1380 },
    { pickup_city: 'Tulsa', pickup_state: 'OK', delivery_city: 'San Antonio', delivery_state: 'TX', miles: 520, rate: 1140 },
  ];

  const routes: RouteRecord[] = routeData.map((r, index) => ({
    id: `demo-route-${String(index + 1).padStart(3, '0')}`,
    org_id: orgId,
    source: 'demo-seed',
    external_id: undefined,
    pickup_city: r.pickup_city,
    pickup_state: r.pickup_state,
    delivery_city: r.delivery_city,
    delivery_state: r.delivery_state,
    rate_total: r.rate,
    miles: r.miles,
    posted_at: '2026-02-01T08:00:00Z',
    created_at: '2026-02-01T08:00:00Z',
  }));

  localStorage.setItem(KEYS.routes, JSON.stringify(routes));
  return routes;
}

export function seedDemoPlanHistory(): PlanHistoryItem[] {
  const history: PlanHistoryItem[] = [
    {
      id: 1001,
      timestamp: '2026-02-05T14:30:00Z',
      snapshot_id: 'demo-snapshot-1001',
      planning_horizon_days: 7,
      plans_generated: 5,
      loads_analyzed: 20,
      execution_time_ms: 342,
      warnings: [],
    },
    {
      id: 1002,
      timestamp: '2026-02-04T10:15:00Z',
      snapshot_id: 'demo-snapshot-1002',
      planning_horizon_days: 7,
      plans_generated: 4,
      loads_analyzed: 18,
      execution_time_ms: 289,
      warnings: [],
    },
    {
      id: 1003,
      timestamp: '2026-02-03T16:45:00Z',
      snapshot_id: 'demo-snapshot-1003',
      planning_horizon_days: 10,
      plans_generated: 5,
      loads_analyzed: 20,
      execution_time_ms: 412,
      warnings: [],
    },
    {
      id: 1004,
      timestamp: '2026-02-02T09:00:00Z',
      snapshot_id: 'demo-snapshot-1004',
      planning_horizon_days: 7,
      plans_generated: 3,
      loads_analyzed: 15,
      execution_time_ms: 198,
      warnings: ['Limited route options in requested radius'],
    },
    {
      id: 1005,
      timestamp: '2026-02-01T11:30:00Z',
      snapshot_id: 'demo-snapshot-1005',
      planning_horizon_days: 14,
      plans_generated: 5,
      loads_analyzed: 20,
      execution_time_ms: 521,
      warnings: [],
    },
  ];

  localStorage.setItem(KEYS.planHistory, JSON.stringify(history));
  return history;
}

export function seedAllDemoData(): void {
  seedDemoOrg();
  seedDemoTruck();
  seedDemoRoutes();
  seedDemoPlanHistory();
}

export function resetDemoData(): void {
  // Remove all demo_v1_* keys
  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith('demo_v1_')) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach((key) => localStorage.removeItem(key));

  // Clear active org/truck
  localStorage.removeItem('active_org_id');
  localStorage.removeItem('active_truck_id');
}

// ---- Sample CSV Data ----

export const SAMPLE_CSV_DATA = `pickup_city,pickup_state,delivery_city,delivery_state,miles,rate_total
Dallas,TX,Houston,TX,240,520
Houston,TX,San Antonio,TX,200,440
San Antonio,TX,Austin,TX,80,200
Austin,TX,Dallas,TX,195,430
Dallas,TX,Oklahoma City,OK,210,480
Oklahoma City,OK,Tulsa,OK,110,260
Tulsa,OK,Little Rock,AR,260,580
Little Rock,AR,New Orleans,LA,400,880
New Orleans,LA,Houston,TX,350,780
Houston,TX,Dallas,TX,240,530`;

// ---- Data Count Helpers ----

export function getDemoDataCounts(): {
  orgs: number;
  trucks: number;
  routes: number;
  planHistory: number;
} {
  const orgs = JSON.parse(localStorage.getItem(KEYS.orgs) || '[]');
  const trucks = JSON.parse(localStorage.getItem(KEYS.trucks) || '[]');
  const routes = JSON.parse(localStorage.getItem(KEYS.routes) || '[]');
  const planHistory = JSON.parse(localStorage.getItem(KEYS.planHistory) || '[]');

  return {
    orgs: orgs.length,
    trucks: trucks.length,
    routes: routes.length,
    planHistory: planHistory.length,
  };
}
