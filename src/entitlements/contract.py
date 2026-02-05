"""
Entitlement Contract — CANONICAL DEFINITION

This is the single source of truth for module entitlements.
Any changes to this file require human approval.
"""

from enum import Enum
from typing import Set


class Tier(str, Enum):
    """Product tiers."""
    BASE = "base"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class Module(str, Enum):
    """Product modules."""
    TRUCK_CORE = "TRUCK_CORE"
    TRUCK_PLAN = "TRUCK_PLAN"
    TRUCK_TRACK = "TRUCK_TRACK"
    TRUCK_LEARN = "TRUCK_LEARN"
    TRUCK_CONNECT = "TRUCK_CONNECT"
    TRUCK_INSIGHT = "TRUCK_INSIGHT"
    TRUCK_FLEET = "TRUCK_FLEET"


# Canonical tier → module mapping
TIER_ENTITLEMENTS: dict[Tier, Set[Module]] = {
    Tier.BASE: {
        Module.TRUCK_CORE,
        Module.TRUCK_PLAN,
        Module.TRUCK_TRACK,
    },
    Tier.PREMIUM: {
        Module.TRUCK_CORE,
        Module.TRUCK_PLAN,
        Module.TRUCK_TRACK,
        Module.TRUCK_LEARN,
        Module.TRUCK_CONNECT,
        Module.TRUCK_INSIGHT,
    },
    Tier.ENTERPRISE: {
        Module.TRUCK_CORE,
        Module.TRUCK_PLAN,
        Module.TRUCK_TRACK,
        Module.TRUCK_LEARN,
        Module.TRUCK_CONNECT,
        Module.TRUCK_INSIGHT,
        Module.TRUCK_FLEET,
    },
}


def get_org_entitlements(org_tier: Tier) -> Set[Module]:
    """Returns modules available for a given tier."""
    return TIER_ENTITLEMENTS[org_tier]


def has_entitlement(org_tier: Tier, module: Module) -> bool:
    """Check if tier grants access to module."""
    return module in TIER_ENTITLEMENTS[org_tier]


def get_minimum_tier_for_module(module: Module) -> Tier:
    """Get the minimum tier required to access a module."""
    for tier in [Tier.BASE, Tier.PREMIUM, Tier.ENTERPRISE]:
        if module in TIER_ENTITLEMENTS[tier]:
            return tier
    return Tier.ENTERPRISE  # Default to highest tier if not found


# Module descriptions for UI/error messages
MODULE_DESCRIPTIONS: dict[Module, str] = {
    Module.TRUCK_CORE: "Core authentication and org management",
    Module.TRUCK_PLAN: "Plan generation and load sequencing",
    Module.TRUCK_TRACK: "Outcome tracking and historical data",
    Module.TRUCK_LEARN: "Prediction calibration and trust scoring",
    Module.TRUCK_CONNECT: "Real load board integrations",
    Module.TRUCK_INSIGHT: "Market analytics and intelligence",
    Module.TRUCK_FLEET: "Multi-truck fleet management",
}


# Upgrade prompts for each premium module
UPGRADE_PROMPTS: dict[Module, dict[str, str]] = {
    Module.TRUCK_LEARN: {
        "title": "Unlock Smarter Predictions",
        "description": (
            "TruckLEARN calibrates predictions based on your actual results. "
            "Over time, the system learns your patterns and becomes more accurate."
        ),
        "cta": "Upgrade to Premium",
    },
    Module.TRUCK_CONNECT: {
        "title": "Real Load Board Data",
        "description": (
            "Connect to DAT, Truckstop, and other load boards for real-time "
            "load availability and market rates."
        ),
        "cta": "Upgrade to Premium",
    },
    Module.TRUCK_INSIGHT: {
        "title": "Market Intelligence",
        "description": (
            "Get lane statistics, market temperature, and negotiation guidance "
            "based on real market data."
        ),
        "cta": "Upgrade to Premium",
    },
    Module.TRUCK_FLEET: {
        "title": "Fleet Management",
        "description": (
            "Manage multiple trucks with fleet-level optimization and "
            "cross-truck analytics."
        ),
        "cta": "Upgrade to Enterprise",
    },
}
