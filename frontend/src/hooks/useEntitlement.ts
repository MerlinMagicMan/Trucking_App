/**
 * Entitlement hook for tier-based feature gating (PREVIEW-001 + DEMO-001)
 *
 * Precedence order:
 * 1. Admin override (grants enterprise)
 * 2. Demo org tier (from localStorage)
 * 3. API org tier
 * 4. Default base
 *
 * Backend is authoritative for entitlements in live mode.
 * Frontend gating is cosmetic only - prevents UI clutter, not security.
 */
import { useState, useEffect } from 'react';
import { getActiveOrgId } from '../services/orgContext';
import { getAdminOverride } from '../services/demoConfig';
import { getDataClient } from '../services/dataClient';

export type Tier = 'base' | 'premium' | 'enterprise';

export interface Entitlement {
  tier: Tier;
  orgId: string | null;
  orgName: string | null;
  isPremium: boolean;
  isEnterprise: boolean;
  isLoading: boolean;
  isAdminOverride: boolean;
  canAccess: (feature: Feature) => boolean;
}

export type Feature =
  | 'copilot'
  | 'intel'
  | 'reports'
  | 'settings'
  | 'maintenance'
  | 'confidence_weighting'
  | 'branch_plans'
  | 'calibration';

// Feature → minimum tier mapping
const FEATURE_TIERS: Record<Feature, Tier> = {
  copilot: 'premium',
  intel: 'premium',
  reports: 'premium',
  settings: 'base',        // All tiers can view settings
  maintenance: 'base',     // Stub visible to all
  confidence_weighting: 'premium',
  branch_plans: 'premium',
  calibration: 'premium',
};

const TIER_LEVELS: Record<Tier, number> = {
  base: 0,
  premium: 1,
  enterprise: 2,
};

export function useEntitlement(): Entitlement {
  // Check admin override SYNCHRONOUSLY to avoid flash of paywall
  // This runs during initial render, before any useEffect
  const adminOverrideActive = getAdminOverride();

  const [tier, setTier] = useState<Tier>(adminOverrideActive ? 'enterprise' : 'base');
  const [orgId, setOrgId] = useState<string | null>(getActiveOrgId());
  const [orgName, setOrgName] = useState<string | null>(adminOverrideActive ? 'Admin Override' : null);
  const [isLoading, setIsLoading] = useState(!adminOverrideActive);
  const [isAdminOverride] = useState(adminOverrideActive);

  useEffect(() => {
    // If admin override is active, we already have correct state - skip
    if (isAdminOverride) {
      return;
    }

    const activeOrgId = getActiveOrgId();
    setOrgId(activeOrgId);

    if (!activeOrgId) {
      setIsLoading(false);
      return;
    }

    // Use dataClient (works in both demo and live modes)
    getDataClient()
      .getOrgs()
      .then((orgs) => {
        const org = orgs.find((o) => o.id === activeOrgId);
        if (org) {
          setOrgName(org.name);
          // Tier comes from org - default to 'base' if not present
          const orgTier = (org as any).tier as Tier | undefined;
          setTier(orgTier || 'base');
        }
      })
      .catch(() => {
        // Backend unavailable - assume base tier
        setTier('base');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [isAdminOverride]);

  const canAccess = (feature: Feature): boolean => {
    // Admin override grants access to everything
    if (isAdminOverride) {
      return true;
    }
    const requiredTier = FEATURE_TIERS[feature];
    return TIER_LEVELS[tier] >= TIER_LEVELS[requiredTier];
  };

  return {
    tier,
    orgId,
    orgName,
    isPremium: tier === 'premium' || tier === 'enterprise',
    isEnterprise: tier === 'enterprise',
    isLoading,
    isAdminOverride,
    canAccess,
  };
}
