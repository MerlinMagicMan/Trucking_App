/**
 * Entitlement hook for tier-based feature gating (PREVIEW-001)
 *
 * Backend is authoritative for entitlements.
 * Frontend gating is cosmetic only - prevents UI clutter, not security.
 */
import { useState, useEffect } from 'react';
import { getActiveOrgId } from '../services/orgContext';
import { fetchOrgs } from '../services/api';

export type Tier = 'base' | 'premium' | 'enterprise';

export interface Entitlement {
  tier: Tier;
  orgId: string | null;
  orgName: string | null;
  isPremium: boolean;
  isEnterprise: boolean;
  isLoading: boolean;
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
  const [tier, setTier] = useState<Tier>('base');
  const [orgId, setOrgId] = useState<string | null>(null);
  const [orgName, setOrgName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const activeOrgId = getActiveOrgId();
    setOrgId(activeOrgId);

    if (!activeOrgId) {
      setIsLoading(false);
      return;
    }

    fetchOrgs()
      .then((orgs) => {
        const org = orgs.find((o) => o.id === activeOrgId);
        if (org) {
          setOrgName(org.name);
          // Tier comes from API response - default to 'base' if not present
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
  }, []);

  const canAccess = (feature: Feature): boolean => {
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
    canAccess,
  };
}
