"""JIRA client for interacting with JIRA issues"""

import logging
from io import BytesIO
from typing import List, Optional
from urllib.parse import urlencode

from jira import JIRA
from jira.resources import Issue

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for JIRA operations"""

    def __init__(
        self,
        server: str,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize JIRA client

        Args:
            server: JIRA server URL
            email: JIRA email (for token auth)
            api_token: JIRA API token (for token auth)
            username: JIRA username (for basic auth)
            password: JIRA password (for basic auth)
        """
        self.server = server

        # Choose authentication method
        if email and api_token:
            self.jira = JIRA(server=server, basic_auth=(email, api_token))
            logger.info(f"Connected to JIRA using API token: {server}")
        elif username and password:
            self.jira = JIRA(server=server, basic_auth=(username, password))
            logger.info(f"Connected to JIRA using username/password: {server}")
        else:
            raise ValueError("Must provide either (email, api_token) or (username, password)")

    def query_issues(self, jql: str, max_results: int = 100) -> List[Issue]:
        """Query JIRA issues using JQL

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return

        Returns:
            List of JIRA issues
        """
        logger.info(f"Querying JIRA with JQL: {jql}")

        # Construct the full URL for debugging
        params = {"jql": jql, "maxResults": max_results}
        query_string = urlencode(params)
        full_url = f"{self.server}/rest/api/2/search?{query_string}"

        # Log the full URL for curl debugging
        logger.debug("=" * 80)
        logger.debug("FULL GET URL FOR CURL:")
        logger.debug(full_url)
        logger.debug("=" * 80)

        # Also log the curl command with auth placeholder
        curl_cmd = f'curl -X GET "{full_url}" -H "Content-Type: application/json" -u "YOUR_EMAIL:YOUR_API_TOKEN"'
        logger.debug("CURL COMMAND:")
        logger.debug(curl_cmd)
        logger.debug("=" * 80)

        issues = self.jira.search_issues(jql, maxResults=max_results)
        logger.info(f"Found {len(issues)} issues")
        return issues

    def query_custom(self, jql: str, max_results: int = 100) -> List[Issue]:
        """Query JIRA issues using custom JQL (alias for query_issues)

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return

        Returns:
            List of JIRA issues
        """
        return self.query_issues(jql, max_results)

    def get_issues_by_status(
        self, project: str, status: str, component: Optional[str] = None
    ) -> List[Issue]:
        """Get issues by project and status

        Args:
            project: JIRA project key
            status: Issue status
            component: Optional component filter

        Returns:
            List of JIRA issues
        """
        jql = f'project = {project} AND status = "{status}"'
        if component:
            jql += f" AND component = {component}"
        return self.query_issues(jql)

    def get_issues_by_label(
        self, project: str, label: str, component: Optional[str] = None
    ) -> List[Issue]:
        """Get issues by project and label

        Args:
            project: JIRA project key
            label: Issue label
            component: Optional component filter

        Returns:
            List of JIRA issues
        """
        jql = f'project = {project} AND labels = "{label}"'
        if component:
            jql += f" AND component = {component}"
        return self.query_issues(jql)

    def get_field_value(self, issue: Issue, field_name: str) -> Optional[str]:
        """Get custom field value from issue

        Args:
            issue: JIRA issue
            field_name: Field name (e.g., 'Version Change')

        Returns:
            Field value or None
        """
        # Handle built-in fields
        if field_name.lower() == "description":
            return issue.fields.description
        if field_name.lower() == "summary":
            return issue.fields.summary

        # Handle custom fields - this may need adjustment based on your JIRA setup
        for field in self.jira.fields():
            if field["name"].lower() == field_name.lower():
                return getattr(issue.fields, field["id"], None)

        logger.warning(f"Field '{field_name}' not found in issue {issue.key}")
        return None

    def add_label(self, issue: Issue, label: str):
        """Add label to issue

        Args:
            issue: JIRA issue
            label: Label to add
        """
        current_labels = issue.fields.labels
        if label not in current_labels:
            current_labels.append(label)
            issue.update(fields={"labels": current_labels})
            logger.info(f"Added label '{label}' to {issue.key}")

    def transition_issue(self, issue: Issue, transition_name: str):
        """Transition issue to new status

        Args:
            issue: JIRA issue
            transition_name: Name of transition (e.g., 'Done', 'In Progress')
        """
        transitions = self.jira.transitions(issue)
        transition_id = None

        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                transition_id = t["id"]
                break

        if transition_id:
            self.jira.transition_issue(issue, transition_id)
            logger.info(f"Transitioned {issue.key} to '{transition_name}'")
        else:
            logger.error(f"Transition '{transition_name}' not found for {issue.key}")
            logger.debug(f"Available transitions: {[t['name'] for t in transitions]}")

    def add_comment(self, issue: Issue, comment: str):
        """Add comment to issue

        Args:
            issue: JIRA issue
            comment: Comment text
        """
        self.jira.add_comment(issue, comment)
        logger.info(f"Added comment to {issue.key}")

    def add_attachment(self, issue: Issue, filename: str, content: str):
        """Add text file attachment to issue

        Args:
            issue: JIRA issue
            filename: Attachment filename
            content: File content as string
        """
        file_obj = BytesIO(content.encode("utf-8"))
        file_obj.name = filename

        self.jira.add_attachment(issue=issue, attachment=file_obj, filename=filename)
        logger.info(f"Added attachment '{filename}' ({len(content)} bytes) to {issue.key}")
