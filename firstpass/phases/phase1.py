"""Phase 1: Monitor regressions and OpenShift payload status"""

import logging
import re
from typing import List, Optional

from jira.resources import Issue

from .base import Phase

logger = logging.getLogger(__name__)


class Phase1(Phase):
    """Phase 1: Check if payload was accepted or rejected using Release Controller"""

    def get_target_issues(self) -> List[Issue]:
        """Get JIRA issues with status configured for Phase 1

        Returns:
            List of JIRA issues
        """
        project = self.config.jira_project
        status = self.get_phase_config("status", "New")
        component = self.config.jira_component

        issues: List[Issue] = self.jira_client.get_issues_by_status(project, status, component)
        return issues

    def extract_payload_tag(self, issue: Issue) -> Optional[str]:
        """Extract payload tag (bad version) from JIRA issue description

        Parses the 'Version Change: GOOD_VERSION → BAD_VERSION' pattern from description.
        The version after the arrow is the regression/bad version (payload tag).

        Args:
            issue: JIRA issue

        Returns:
            Payload tag (bad version) or None
        """
        # Get description
        description = self.jira_client.get_field_value(issue, "description")

        if description:
            # Pattern: *Version Change:* X → Y or *Version Change:* X -> Y
            # Asterisks indicate bold formatting in JIRA
            # We want Y (the bad/regression version after the arrow)
            # Use \S+ to match non-whitespace (includes hyphens in version strings)
            pattern = r"\*?Version Change:?\*?\s*(\S+)\s*(?:→|->)\s*(\S+)"
            match = re.search(pattern, description, re.IGNORECASE)

            if match:
                good_version = match.group(1).strip()
                bad_version = match.group(2).strip()
                self.logger.info(
                    f"Extracted from Version Change: good={good_version}, bad={bad_version}"
                )
                return bad_version

        # Fallback: try to extract from affected versions or fix versions
        if hasattr(issue.fields, "versions") and issue.fields.versions:
            payload_tag = str(issue.fields.versions[0].name)
            self.logger.info(f"Extracted payload tag from versions: {payload_tag}")
            return payload_tag

        if hasattr(issue.fields, "fixVersions") and issue.fields.fixVersions:
            payload_tag = str(issue.fields.fixVersions[0].name)
            self.logger.info(f"Extracted payload tag from fixVersions: {payload_tag}")
            return payload_tag

        self.logger.warning(f"Could not extract payload tag from {issue.key}")
        return None

    def process_issue(self, issue: Issue) -> bool:
        """Process a single JIRA issue

        Args:
            issue: JIRA issue to process

        Returns:
            True if processing was successful, False otherwise
        """
        self.logger.info(f"Processing issue {issue.key}: {issue.fields.summary}")

        # Step 1: Extract build URL from JIRA description
        description = self.jira_client.get_field_value(issue, "description")
        build_url = self.release_controller_client.extract_build_url_from_description(description)

        if not build_url:
            self.logger.warning(f"{issue.key}: Could not find build URL in description - skipping")
            return False

        # Step 2: Fetch build-log.txt
        build_log = self.release_controller_client.fetch_build_log(build_url)

        if not build_log:
            self.logger.warning(f"{issue.key}: Could not fetch build log - skipping")
            return False

        # Step 3: Extract payload tag from JIRA (needed for stream extraction in forced execution cases)
        payload_tag = self.extract_payload_tag(issue)

        if not payload_tag:
            self.logger.warning(f"{issue.key}: Could not extract payload tag - skipping")
            return False

        # Step 4: Extract release stream from build log (pass payload_tag for forced execution support)
        stream = self.release_controller_client.extract_release_stream(build_log, payload_tag)

        if not stream:
            self.logger.warning(f"{issue.key}: Could not extract release stream - skipping")
            return False

        # Step 5: Query Release Controller for release phase
        phase = self.release_controller_client.get_release_phase(stream, payload_tag)

        if not phase:
            self.logger.warning(f"{issue.key}: Could not get release phase - skipping")
            return False

        # Step 6: Take action based on phase
        phase_lower = phase.lower()

        if phase_lower == "rejected":
            transition_name = self.get_phase_config("transition_done", "Done")
            self.logger.info(
                f"{issue.key}: Payload {payload_tag} was REJECTED - moving to {transition_name}"
            )

            if self.dry_run:
                self.logger.warning(
                    f"[DRY RUN] Would add comment to {issue.key}: "
                    f"Payload {payload_tag} was rejected by Release Controller. "
                    f"Stream: {stream}, Phase: {phase}"
                )
                self.logger.warning(
                    f"[DRY RUN] Would transition {issue.key} to '{transition_name}'"
                )
            else:
                self.jira_client.add_comment(
                    issue,
                    f"Payload {payload_tag} was rejected by Release Controller. "
                    f"Stream: {stream}, Phase: {phase}",
                )
                self.jira_client.transition_issue(issue, transition_name)
            return True

        elif phase_lower == "accepted":
            label = self.get_phase_config("label", "phase1_done")
            self.logger.info(
                f"{issue.key}: Payload {payload_tag} was ACCEPTED - advancing to Phase 2"
            )

            markdown_report = None
            if self.perf_keeper_client:
                prow_job_url = self.release_controller_client.extract_prow_job_url(description)
                if prow_job_url:
                    self.logger.info(f"{issue.key}: Calling perf-keeper for analysis")
                    analysis_result = self.perf_keeper_client.analyze_job(prow_job_url)
                    if analysis_result and not analysis_result.get("passed"):
                        markdown_report = analysis_result.get("analysis", "")

            if markdown_report:
                filename = f"regression-analysis-{issue.key}.md"
                if self.dry_run:
                    preview = (
                        markdown_report[:500] + "..."
                        if len(markdown_report) > 500
                        else markdown_report
                    )
                    self.logger.warning(f"[DRY RUN] Would attach '{filename}' to {issue.key}")
                    self.logger.info(f"Report preview:\n{preview}")
                else:
                    try:
                        self.jira_client.add_attachment(issue, filename, markdown_report)
                        self.logger.info(f"{issue.key}: Attached analysis report")
                    except Exception as e:
                        self.logger.error(f"{issue.key}: Failed to attach report: {e}")

            comment_text = (
                f"Payload {payload_tag} was accepted by Release Controller. "
                f"Stream: {stream}, Phase: {phase}. Moving to Phase 2 for analysis."
            )
            if markdown_report:
                comment_text += "\n\nRegression analysis report has been attached."

            if self.dry_run:
                self.logger.warning(f"[DRY RUN] Would add comment to {issue.key}: {comment_text}")
                self.logger.warning(f"[DRY RUN] Would add label '{label}' to {issue.key}")
            else:
                self.jira_client.add_comment(issue, comment_text)
                self.jira_client.add_label(issue, label)

            return True

        else:
            self.logger.info(
                f"{issue.key}: Payload {payload_tag} is in phase '{phase}' - leaving in NEW"
            )
            return True
