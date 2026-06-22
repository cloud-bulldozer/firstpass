"""Tests for PerfKeeperClient"""

from unittest.mock import Mock, patch

import httpx

from firstpass.perf_keeper_client import PerfKeeperClient


class TestPerfKeeperClient:
    """Test PerfKeeperClient class"""

    def test_init(self):
        """Test client initialization"""
        client = PerfKeeperClient(base_url="http://localhost:8080", timeout=120)

        assert client.base_url == "http://localhost:8080"
        assert client.timeout == 120
        assert client.api_token is None
        assert client.client is not None

    def test_init_with_api_token(self):
        """Test client initialization with API token"""
        client = PerfKeeperClient(
            base_url="http://localhost:8080", timeout=120, api_token="test-token"
        )

        assert client.api_token == "test-token"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from base_url"""
        client = PerfKeeperClient(base_url="http://localhost:8080/")

        assert client.base_url == "http://localhost:8080"

    @patch("firstpass.perf_keeper_client.httpx.Client")
    def test_analyze_job_success(self, mock_http_client):
        """Test successful job analysis"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "passed": False,
            "analysis": "# Analysis\n\nRegression found.",
            "analysis_duration_seconds": 45,
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_http_client.return_value = mock_client_instance

        client = PerfKeeperClient(base_url="http://localhost:8080")
        result = client.analyze_job("https://prow.ci.openshift.org/view/gs/test/123")

        assert result is not None
        assert result["passed"] is False
        assert "Regression found" in result["analysis"]
        assert result["analysis_duration_seconds"] == 45

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args.args[0] == "http://localhost:8080/analyze"
        assert (
            call_args.kwargs["json"]["job_url"] == "https://prow.ci.openshift.org/view/gs/test/123"
        )

    @patch("firstpass.perf_keeper_client.httpx.Client")
    def test_analyze_job_passed(self, mock_http_client):
        """Test analysis when job passed"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "passed": True,
            "analysis": "Job passed. No diagnosis required.",
            "analysis_duration_seconds": 5,
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_http_client.return_value = mock_client_instance

        client = PerfKeeperClient(base_url="http://localhost:8080")
        result = client.analyze_job("https://prow.ci.openshift.org/view/gs/test/123")

        assert result is not None
        assert result["passed"] is True

    @patch("firstpass.perf_keeper_client.httpx.Client")
    def test_analyze_job_timeout(self, mock_http_client):
        """Test handling of timeout exception"""
        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = httpx.TimeoutException("Request timed out")
        mock_http_client.return_value = mock_client_instance

        client = PerfKeeperClient(base_url="http://localhost:8080", timeout=5)
        result = client.analyze_job("https://prow.ci.openshift.org/view/gs/test/123")

        assert result is None

    @patch("firstpass.perf_keeper_client.httpx.Client")
    def test_analyze_job_http_error(self, mock_http_client):
        """Test handling of HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )
        mock_http_client.return_value = mock_client_instance

        client = PerfKeeperClient(base_url="http://localhost:8080")
        result = client.analyze_job("https://prow.ci.openshift.org/view/gs/test/123")

        assert result is None

    @patch("firstpass.perf_keeper_client.httpx.Client")
    def test_analyze_job_request_error(self, mock_http_client):
        """Test handling of request error"""
        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = httpx.RequestError("Connection failed")
        mock_http_client.return_value = mock_client_instance

        client = PerfKeeperClient(base_url="http://localhost:8080")
        result = client.analyze_job("https://prow.ci.openshift.org/view/gs/test/123")

        assert result is None

    @patch("firstpass.perf_keeper_client.httpx.Client")
    def test_analyze_job_unexpected_error(self, mock_http_client):
        """Test handling of unexpected error"""
        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = Exception("Unexpected error")
        mock_http_client.return_value = mock_client_instance

        client = PerfKeeperClient(base_url="http://localhost:8080")
        result = client.analyze_job("https://prow.ci.openshift.org/view/gs/test/123")

        assert result is None

    @patch("firstpass.perf_keeper_client.httpx.Client")
    def test_context_manager(self, mock_http_client):
        """Test using client as context manager"""
        mock_client_instance = Mock()
        mock_http_client.return_value = mock_client_instance

        with PerfKeeperClient(base_url="http://localhost:8080") as client:
            assert client is not None

        mock_client_instance.close.assert_called_once()
