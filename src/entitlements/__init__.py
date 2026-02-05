"""
Entitlement contract module — CANONICAL DEFINITION.

This module defines the single source of truth for module entitlements.
"""

from .contract import (
    Tier,
    Module,
    TIER_ENTITLEMENTS,
    get_org_entitlements,
    has_entitlement,
    get_minimum_tier_for_module,
)

__all__ = [
    "Tier",
    "Module",
    "TIER_ENTITLEMENTS",
    "get_org_entitlements",
    "has_entitlement",
    "get_minimum_tier_for_module",
]
