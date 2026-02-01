/**
 * Org and truck context utilities (Phase 2A)
 * Stores active org/truck in localStorage for header injection
 */

const ORG_KEY = 'active_org_id';
const TRUCK_KEY = 'active_truck_id';

export function getActiveOrgId(): string | null {
  return localStorage.getItem(ORG_KEY);
}

export function setActiveOrgId(id: string): void {
  localStorage.setItem(ORG_KEY, id);
}

export function getActiveTruckId(): string | null {
  return localStorage.getItem(TRUCK_KEY);
}

export function setActiveTruckId(id: string): void {
  localStorage.setItem(TRUCK_KEY, id);
}
