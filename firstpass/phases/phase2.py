"""Phase 2: Commit triage for regression root cause identification"""

import logging
from typing import List

from jira.resources import Issue

from .base import Phase

logger = logging.getLogger(__name__)


class Phase2(Phase):
    """Phase 2: Rank commits by likelihood of causing the regression"""

    def get_target_issues(self) -> List[Issue]:
        """Get issues in progress that have completed Phase 1."""
        project = self.config.jira_project
        status = self.get_phase_config("status", "In Progress")
        label_required = self.get_phase_config("label_required", "phase1_done")
        component = self.config.jira_component

        jql = f'project = {project} AND status = "{status}" AND labels = "{label_required}"'
        if component:
            jql += f' AND component = "{component}"'

        return self.jira_client.query_issues(jql)

    def process_issue(self, issue: Issue) -> bool:
        """Run commit triage, attach the report, and label the issue phase2_done."""
        self.logger.info(f"Processing {issue.key}: {issue.fields.summary}")

        if not self.perf_keeper_client:
            self.logger.error(f"{issue.key}: perf-keeper client not configured")
            return False

        success = self.perf_keeper_client.analyze_commits(issue.key)
        if not success:
            self.logger.error(f"{issue.key}: commit triage failed")
            return False

        label = self.get_phase_config("label", "phase2_done")

        if self.dry_run:
            self.logger.warning(f"[DRY RUN] Would add label '{label}' to {issue.key}")
        else:
            self.jira_client.add_label(issue, label)

        return True
