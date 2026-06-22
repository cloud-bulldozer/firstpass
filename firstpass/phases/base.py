"""Base phase class for FirstPass Agent"""

import logging
from abc import ABC, abstractmethod
from typing import List

from jira.resources import Issue

logger = logging.getLogger(__name__)


class Phase(ABC):
    """Base class for all phases"""

    def __init__(
        self,
        config,
        jira_client,
        release_controller_client,
        phase_name: str,
        dry_run: bool = False,
        perf_keeper_client=None,
    ):
        """Initialize phase

        Args:
            config: Configuration object
            jira_client: JIRA client instance
            release_controller_client: Release Controller client instance
            phase_name: Name of this phase (e.g., 'phase1')
            dry_run: If True, no JIRA updates will be made
            perf_keeper_client: Optional perf-keeper client instance
        """
        self.config = config
        self.jira_client = jira_client
        self.release_controller_client = release_controller_client
        self.phase_name = phase_name
        self.dry_run = dry_run
        self.perf_keeper_client = perf_keeper_client
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_phase_config(self, key: str, default=None):
        """Get phase-specific configuration value

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        return self.config.get(f"phases.{self.phase_name}.{key}", default)

    @abstractmethod
    def get_target_issues(self) -> List[Issue]:
        """Get list of JIRA issues to process in this phase

        Returns:
            List of JIRA issues
        """
        pass

    @abstractmethod
    def process_issue(self, issue: Issue) -> bool:
        """Process a single JIRA issue

        Args:
            issue: JIRA issue to process

        Returns:
            True if processing was successful, False otherwise
        """
        pass

    def run(self):
        """Execute the phase"""
        self.logger.info(f"Starting {self.__class__.__name__}")

        issues = self.get_target_issues()

        if not issues:
            self.logger.info("No issues to process")
            return

        self.logger.info(f"Processing {len(issues)} issues")

        processed = 0
        failed = 0

        for issue in issues:
            try:
                self.logger.info(f"Processing {issue.key}")
                success = self.process_issue(issue)

                if success:
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                self.logger.error(f"Error processing {issue.key}: {e}", exc_info=True)
                failed += 1

        self.logger.info(f"Phase complete - Processed: {processed}, Failed: {failed}")
