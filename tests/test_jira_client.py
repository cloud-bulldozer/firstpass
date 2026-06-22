"""Tests for JiraClient"""

from unittest.mock import Mock, patch

from firstpass.jira_client import JiraClient


class TestJiraClient:
    """Test JiraClient class"""

    @patch("firstpass.jira_client.JIRA")
    def test_init_with_api_token(self, mock_jira):
        """Test initialization with email and API token"""
        _ = JiraClient(
            server="https://test.atlassian.net", email="test@example.com", api_token="test-token"
        )

        mock_jira.assert_called_once()
        call_kwargs = mock_jira.call_args.kwargs

        assert call_kwargs["server"] == "https://test.atlassian.net"
        assert "basic_auth" in call_kwargs
        assert call_kwargs["basic_auth"] == ("test@example.com", "test-token")

    @patch("firstpass.jira_client.JIRA")
    def test_init_with_username_password(self, mock_jira):
        """Test initialization with username and password"""
        _ = JiraClient(
            server="https://test.atlassian.net", username="testuser", password="testpass"
        )

        mock_jira.assert_called_once()
        call_kwargs = mock_jira.call_args.kwargs

        assert call_kwargs["server"] == "https://test.atlassian.net"
        assert "basic_auth" in call_kwargs
        assert call_kwargs["basic_auth"] == ("testuser", "testpass")

    @patch("firstpass.jira_client.JIRA")
    def test_query_issues(self, mock_jira):
        """Test querying issues"""
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance

        mock_issues = [Mock(key="TEST-1"), Mock(key="TEST-2")]
        mock_jira_instance.search_issues.return_value = mock_issues

        client = JiraClient(
            server="https://test.atlassian.net", email="test@example.com", api_token="test-token"
        )

        jql = 'project = TEST AND status = "New"'
        results = client.query_issues(jql, max_results=10)

        mock_jira_instance.search_issues.assert_called_once_with(jql, maxResults=10)
        assert len(results) == 2
        assert results[0].key == "TEST-1"

    @patch("firstpass.jira_client.JIRA")
    def test_query_issues_default_max_results(self, mock_jira):
        """Test query_issues uses default max_results"""
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance
        mock_jira_instance.search_issues.return_value = []

        client = JiraClient(
            server="https://test.atlassian.net", email="test@example.com", api_token="test-token"
        )

        jql = "project = TEST"
        client.query_issues(jql)

        call_args = mock_jira_instance.search_issues.call_args
        assert call_args.kwargs["maxResults"] == 100

    @patch("firstpass.jira_client.JIRA")
    def test_add_attachment(self, mock_jira):
        """Test adding attachment to issue"""
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance

        client = JiraClient(
            server="https://test.atlassian.net", email="test@example.com", api_token="test-token"
        )

        mock_issue = Mock(key="TEST-123")
        content = "# Test Report\n\nThis is a test markdown report."
        filename = "test-report.md"

        client.add_attachment(mock_issue, filename, content)

        mock_jira_instance.add_attachment.assert_called_once()
        call_args = mock_jira_instance.add_attachment.call_args

        assert call_args.kwargs["issue"] == mock_issue
        assert call_args.kwargs["filename"] == filename

        attachment_obj = call_args.kwargs["attachment"]
        assert attachment_obj.name == filename
        assert attachment_obj.read().decode("utf-8") == content
