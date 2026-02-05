#!/usr/bin/env python3
"""
CLI for the AI Development Team.

Usage:
    dev-team feature "Add DAT load board integration"
    dev-team review app/services/calibration.py
    dev-team audit algorithm
    dev-team audit imports
    dev-team check-boundaries
    dev-team health
    dev-team escalations
    dev-team approve <index> --approver "your-name"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents import Orchestrator
from src.agents.types import AgentRole


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_json(data: dict, indent: int = 2):
    """Print formatted JSON."""
    print(json.dumps(data, indent=indent, default=str))


async def cmd_feature(args):
    """Process a feature request."""
    print_header(f"Feature: {args.description}")

    orchestrator = Orchestrator()
    result = await orchestrator.process_request(args.description)

    print_json(result)

    if result.get("status") == "vetoed":
        print("\n⚠️  Feature was VETOED by Product Guardian")
        print(f"   Reason: {result.get('reason')}")
        print("   Requires human override to proceed.")

    elif result.get("status") == "escalation_required":
        print("\n⚠️  Feature requires HUMAN APPROVAL")
        print("   Run 'dev-team escalations' to see pending approvals")

    elif result.get("status") == "blocked":
        print("\n❌ Feature was BLOCKED by QA")
        print(f"   Issues: {result.get('qa_result', {}).get('blocking_issues')}")

    else:
        print("\n✅ Feature processing complete")


async def cmd_review(args):
    """Review a code file."""
    print_header(f"Code Review: {args.file}")

    orchestrator = Orchestrator()
    qa = orchestrator.agents[AgentRole.QA_ENGINEER]

    result = await qa.review_code(args.file)

    print(f"File: {result.file_path}")
    print(f"Decision: {result.merge_decision}")

    if result.blocking_issues:
        print("\n❌ Blocking Issues:")
        for issue in result.blocking_issues:
            print(f"  - [{issue.get('category')}] {issue.get('issue')}")
            print(f"    Fix: {issue.get('fix')}")

    if result.major_issues:
        print("\n⚠️  Major Issues:")
        for issue in result.major_issues:
            print(f"  - [{issue.get('category')}] {issue.get('issue')}")

    if not result.blocking_issues and not result.major_issues:
        print("\n✅ No issues found")


async def cmd_audit(args):
    """Run an audit."""
    print_header(f"Audit: {args.type}")

    orchestrator = Orchestrator()

    if args.type == "algorithm":
        # Run architecture observer scan for algorithm issues
        observer = orchestrator.agents[AgentRole.ARCHITECTURE_OBSERVER]
        signals = await observer.scan_codebase()

        algo_signals = [s for s in signals if "determinism" in s.observation_type]

        print(f"Found {len(algo_signals)} algorithm-related issues:\n")
        for signal in algo_signals:
            print(f"  [{signal.severity.value}] {signal.summary}")
            for e in signal.evidence:
                print(f"    - {e}")
            print(f"    Recommendation: {signal.recommendation}")
            print()

    elif args.type == "imports":
        # Check import boundaries
        result = await orchestrator.audit_boundaries()

        print(f"Import Violations: {len(result.get('import_violations', []))}")
        for v in result.get("import_violations", []):
            print(f"  ❌ {v}")

        print(f"\nDecimal Violations: {len(result.get('decimal_violations', []))}")
        for v in result.get("decimal_violations", []):
            print(f"  ❌ {v}")

        print(f"\nEntitlement Issues: {len(result.get('entitlement_issues', []))}")
        for v in result.get("entitlement_issues", []):
            print(f"  ❌ {v}")

    else:
        # General audit
        result = await orchestrator.audit_boundaries()
        print_json(result)


async def cmd_boundaries(args):
    """Check module boundaries."""
    print_header("Module Boundary Check")

    orchestrator = Orchestrator()
    result = await orchestrator.audit_boundaries()

    total_issues = (
        len(result.get("import_violations", [])) +
        len(result.get("decimal_violations", [])) +
        len(result.get("entitlement_issues", []))
    )

    if total_issues == 0:
        print("✅ All boundaries are clean!")
    else:
        print(f"❌ Found {total_issues} boundary issues")
        print_json(result)


async def cmd_health(args):
    """Check system health."""
    print_header("System Health")

    orchestrator = Orchestrator()
    result = await orchestrator.check_health()

    print_json(result)

    print("\n✅ All agents initialized and ready")


async def cmd_escalations(args):
    """Show pending escalations."""
    print_header("Pending Escalations")

    orchestrator = Orchestrator()
    escalations = orchestrator.get_pending_escalations()

    if not escalations:
        print("No pending escalations.")
        return

    for i, esc in enumerate(escalations):
        print(f"\n[{i}] {esc['reason']}")
        print(f"    What: {esc['what']}")
        print(f"    Why: {esc['why']}")
        print(f"    Requested by: {esc['requested_by']}")
        print(f"    Time: {esc['timestamp']}")

    print(f"\nTotal: {len(escalations)} pending escalations")
    print("\nTo approve: dev-team approve <index> --approver 'your-name'")


async def cmd_approve(args):
    """Approve an escalation."""
    print_header(f"Approve Escalation #{args.index}")

    orchestrator = Orchestrator()
    success = await orchestrator.approve_escalation(args.index, args.approver)

    if success:
        print(f"✅ Escalation #{args.index} approved by {args.approver}")
    else:
        print(f"❌ Failed to approve escalation #{args.index}")
        print("   Check that the index is valid with 'dev-team escalations'")


def create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="AI Development Team CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    dev-team feature "Add user preferences"
    dev-team review backend/app/api/routes.py
    dev-team audit imports
    dev-team check-boundaries
    dev-team health
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # feature command
    feature_parser = subparsers.add_parser("feature", help="Process a feature request")
    feature_parser.add_argument("description", help="Feature description")

    # review command
    review_parser = subparsers.add_parser("review", help="Review a code file")
    review_parser.add_argument("file", help="File path to review")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Run an audit")
    audit_parser.add_argument(
        "type",
        choices=["algorithm", "imports", "all"],
        help="Type of audit",
    )

    # check-boundaries command
    subparsers.add_parser("check-boundaries", help="Check module boundaries")

    # health command
    subparsers.add_parser("health", help="Check system health")

    # escalations command
    subparsers.add_parser("escalations", help="Show pending escalations")

    # approve command
    approve_parser = subparsers.add_parser("approve", help="Approve an escalation")
    approve_parser.add_argument("index", type=int, help="Escalation index")
    approve_parser.add_argument("--approver", required=True, help="Approver name")

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Map commands to handlers
    handlers = {
        "feature": cmd_feature,
        "review": cmd_review,
        "audit": cmd_audit,
        "check-boundaries": cmd_boundaries,
        "health": cmd_health,
        "escalations": cmd_escalations,
        "approve": cmd_approve,
    }

    handler = handlers.get(args.command)
    if handler:
        asyncio.run(handler(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
