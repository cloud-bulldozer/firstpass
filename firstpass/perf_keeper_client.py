"""Client for perf-keeper analysis service"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class PerfKeeperClient:
    """Client for perf-keeper diagnosis service"""

    def __init__(self, base_url: str, timeout: int = 120):
        """Initialize perf-keeper client

        Args:
            base_url: Perf-keeper service base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        transport = httpx.HTTPTransport(retries=3)

        self.client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)

    def analyze_job(self, job_url: str) -> Optional[Dict[str, Any]]:
        """Analyze Prow job and return markdown report

        Args:
            job_url: Prow job URL

        Returns:
            Dict with 'passed', 'analysis', and 'analysis_duration_seconds' keys, or None on failure
        """
        endpoint = f"{self.base_url}/analyze"
        payload = {"job_url": job_url}

        try:
            response = self.client.post(endpoint, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error(f"Perf-keeper request timed out after {self.timeout}s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Perf-keeper HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Perf-keeper request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling perf-keeper: {e}", exc_info=True)
            return None

    def analyze_commits(self, jira_key: str) -> bool:
        """Run Phase 2 commit triage for the given JIRA issue.

        Args:
            jira_key: JIRA issue key (e.g. PERFSCALE-5204)

        Returns:
            True if the pipeline ran and uploaded the report successfully, False otherwise
        """
        endpoint = f"{self.base_url}/analyze-commits"
        payload = {"jira_key": jira_key}

        try:
            response = self.client.post(endpoint, json=payload)
            response.raise_for_status()
            return response.json().get("status") == "ok"
        except httpx.TimeoutException:
            logger.error(f"Perf-keeper analyze-commits timed out after {self.timeout}s")
            return False
        except httpx.HTTPStatusError as e:
            logger.error(f"Perf-keeper HTTP error: {e.response.status_code} - {e.response.text}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Perf-keeper request error: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error calling perf-keeper analyze-commits: {e}", exc_info=True
            )
            return False

    def close(self):
        """Close HTTP client and clean up resources"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
