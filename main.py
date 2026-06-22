#!/usr/bin/env python3
"""
FirstPass Agent - Entry Point

Multi-Phase Agent for OpenShift Performance Regression Triage
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from firstpass.framework import FirstPassFramework


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="FirstPass Agent - OpenShift Performance Regression Triage"
    )

    parser.add_argument(
        "--config", default="config.yaml", help="Path to configuration file (default: config.yaml)"
    )

    parser.add_argument(
        "--phase",
        choices=["phase1", "phase2"],
        help="Run specific phase only (default: run all enabled phases)",
    )

    parser.add_argument("--dry-run", action="store_true", help="Dry run mode - no JIRA updates")

    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate regression report from open JIRA issues",
    )

    args = parser.parse_args()

    # Initialize framework
    framework = FirstPassFramework(config_path=args.config, dry_run=args.dry_run)

    try:
        # Run report or normal processing
        if args.report:
            framework.generate_report()
        else:
            framework.run(phase=args.phase)
    finally:
        framework.cleanup()


if __name__ == "__main__":
    main()
