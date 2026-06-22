"""Release Controller API client"""

import logging
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class ReleaseControllerClient:
    """Client for OpenShift Release Controller API"""

    def __init__(self, base_url: str, gcs_base_url: str):
        """Initialize Release Controller client

        Args:
            base_url: Release Controller API base URL
            gcs_base_url: GCS web base URL
        """
        self.base_url = base_url
        self.gcs_base_url = gcs_base_url
        self.session = requests.Session()

    def fetch_build_log(self, build_url: str) -> Optional[str]:
        """Fetch build-log.txt from GCS

        Args:
            build_url: Full URL to build-log.txt

        Returns:
            Build log content or None if fetch fails
        """
        try:
            logger.info(f"Fetching build log from: {build_url}")
            response = self.session.get(build_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch build log: {e}")
            return None

    def extract_release_stream(
        self, build_log: str, payload_tag: Optional[str] = None
    ) -> Optional[str]:
        """Extract release stream from build log

        Args:
            build_log: Build log content
            payload_tag: Optional payload tag to construct stream for forced executions

        Returns:
            Release stream (e.g., '5.0.0-0.nightly') or None
        """
        # Pattern: Requesting a release from https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/5.0.0-0.nightly/latest
        pattern = r"Requesting a release from https://[^/]+/api/v1/releasestream/([^/]+)/latest"

        match = re.search(pattern, build_log)
        if match:
            stream = match.group(1)
            logger.info(f"Extracted release stream: {stream}")
            return stream

        # Check for forced execution (explicitly provided pull-spec)
        if "Using explicitly provided pull-spec" in build_log:
            logger.info("Detected forced execution with explicit pull-spec")

            if payload_tag:
                # Extract short version from payload_tag (e.g., "4.22" from "4.22.0-0.nightly-2026-05-11-043758")
                # Pattern: Match major.minor at the beginning of the payload tag
                version_pattern = r"^(\d+\.\d+)"
                version_match = re.match(version_pattern, payload_tag)

                if version_match:
                    short_version = version_match.group(1)
                    constructed_stream = f"{short_version}.0-0.nightly"
                    logger.info(f"Constructed stream from payload tag: {constructed_stream}")
                    return constructed_stream
                else:
                    logger.warning(
                        f"Could not extract short version from payload tag: {payload_tag}"
                    )
            else:
                logger.warning(
                    "Forced execution detected but no payload_tag provided to construct stream"
                )

        logger.warning("Could not extract release stream from build log")
        return None

    def get_release_info(self, stream: str, payload_tag: str) -> Optional[Dict[str, Any]]:
        """Get release information from Release Controller

        Args:
            stream: Release stream (e.g., '5.0.0-0.nightly')
            payload_tag: Payload tag (e.g., '5.0.0-0.nightly-2026-05-11-043758')

        Returns:
            Release info dictionary or None if request fails
        """
        url = f"{self.base_url}/releasestream/{stream}/release/{payload_tag}"

        try:
            logger.debug("=" * 80)
            logger.debug("Querying Release Controller")
            logger.debug(f"Full URL: {url}")
            logger.debug(f"Stream: {stream}")
            logger.debug(f"Payload Tag: {payload_tag}")
            logger.debug("=" * 80)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            data: Dict[str, Any] = response.json()
            logger.info(f"Release info retrieved for {payload_tag}")
            return data
        except requests.RequestException as e:
            logger.error(f"Failed to query Release Controller: {e}")
            return None

    def get_release_phase(self, stream: str, payload_tag: str) -> Optional[str]:
        """Get release phase from Release Controller

        Args:
            stream: Release stream
            payload_tag: Payload tag

        Returns:
            Release phase (e.g., 'Accepted', 'Rejected', 'Pending') or None
        """
        release_info = self.get_release_info(stream, payload_tag)

        if release_info and "phase" in release_info:
            phase = str(release_info["phase"])
            logger.info(f"Release phase for {payload_tag}: {phase}")
            return phase

        return None

    def extract_build_url_from_description(self, description: str) -> Optional[str]:
        """Extract build-log.txt URL from JIRA description

        Converts Prow URL to GCS build-log.txt URL:
        - Prow: https://prow.ci.openshift.org/view/gs/origin-ci-test/logs/{job}/{id}
        - GCS:  https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/origin-ci-test/logs/{job}/{id}/build-log.txt

        Args:
            description: JIRA issue description

        Returns:
            Build log URL or None
        """
        if not description:
            return None

        # Pattern: Look for Prow URL
        # Example: https://prow.ci.openshift.org/view/gs/origin-ci-test/logs/periodic-ci-.../2053857063406145536
        # Exclude common markdown/URL-ending characters: ], ), >, etc.
        prow_pattern = r"https://prow\.ci\.openshift\.org/view/gs/([^\s\]\)\>]+)"

        match = re.search(prow_pattern, description)
        if match:
            # Extract the path after /gs/
            gcs_path = match.group(1)

            # Convert to gcsweb URL with build-log.txt
            gcsweb_url = f"{self.gcs_base_url}/{gcs_path}/build-log.txt"
            logger.info(f"Extracted Prow URL and converted to GCS: {gcsweb_url}")
            return gcsweb_url

        # Fallback: Look for direct gcsweb URL ending in build-log.txt
        gcsweb_pattern = r"(https://gcsweb[^\s]+/build-log\.txt)"
        match = re.search(gcsweb_pattern, description)
        if match:
            url = match.group(1)
            logger.info(f"Extracted direct GCS build URL: {url}")
            return url

        logger.warning("Could not extract build URL from description")
        return None

    def extract_prow_job_url(self, description: str) -> Optional[str]:
        """Extract Prow job URL from JIRA description

        Args:
            description: JIRA issue description

        Returns:
            Prow job URL or None
        """
        if not description:
            return None

        prow_pattern = r"(https://prow\.ci\.openshift\.org/view/gs/[^\s\]\)\>]+)"

        match = re.search(prow_pattern, description)
        if match:
            url = match.group(1)
            logger.info(f"Extracted Prow job URL: {url}")
            return url

        logger.warning("Could not extract Prow job URL from description")
        return None
