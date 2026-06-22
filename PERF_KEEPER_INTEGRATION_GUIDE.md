# Perf-Keeper Integration Implementation Guide

## Overview

This document provides detailed step-by-step instructions for integrating perf-keeper analysis into FirstPass Phase1.

### Goal

When Phase1 determines a payload is "Accepted", automatically generate a comprehensive markdown analysis report via perf-keeper and attach it to the JIRA issue for Phase2 analysis.

### Architecture

```
Phase1 Processing Flow:
┌─────────────────────────────────────────────────────────────────┐
│ 1. Query JIRA for "New" issues                                  │
│ 2. Extract build URL, payload tag, stream                       │
│ 3. Query Release Controller for payload phase                   │
│                                                                 │
│ If phase == "Accepted":                                         │
│   ├─ Extract Prow job URL from JIRA description                 │
│   ├─ Call perf-keeper POST /analyze with Prow URL               │
│   ├─ Receive markdown analysis report                           │
│   ├─ Upload markdown as JIRA attachment                         │
│   ├─ Add comment to JIRA                                        │
│   └─ Add "phase1_done" label                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Components Modified

1. `firstpass/perf_keeper_client.py` - **NEW**
2. `firstpass/jira_client.py` - **MODIFY**
3. `firstpass/release_controller.py` - **MODIFY**
4. `firstpass/phases/base.py` - **MODIFY**
5. `firstpass/phases/phase1.py` - **MODIFY**
6. `firstpass/framework.py` - **MODIFY**
7. `config.yaml` - **MODIFY**
8. `requirements.txt` - **MODIFY**

---

## Implementation Steps

### Step 1: Create PerfKeeperClient

**File**: `firstpass/perf_keeper_client.py`

**Purpose**: HTTP client for perf-keeper's `/analyze` endpoint.

**Implementation**:

```python
"""Client for perf-keeper analysis service"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class PerfKeeperClient:
    """Client for perf-keeper diagnosis service"""

    def __init__(self, base_url: str, timeout: int = 120, api_token: Optional[str] = None):
        """Initialize perf-keeper client

        Args:
            base_url: Perf-keeper service base URL (e.g., "http://perf-keeper:8080")
            timeout: Request timeout in seconds (default: 120)
            api_token: Optional API token for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_token = api_token

        # Setup httpx client with retries
        transport = httpx.HTTPTransport(retries=3)
        headers = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        self.client = httpx.Client(
            transport=transport,
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        )

        logger.info(f"Initialized PerfKeeperClient: {self.base_url}")

    def analyze_job(self, job_url: str) -> Optional[dict[str, Any]]:
        """Analyze Prow job and return markdown report

        Args:
            job_url: Prow job URL (e.g., "https://prow.ci.openshift.org/view/gs/...")

        Returns:
            Dict with keys:
                - passed (bool): Whether the job passed
                - analysis (str): Markdown analysis report
                - analysis_duration_seconds (int): Time taken
            Returns None if request fails
        """
        endpoint = f"{self.base_url}/analyze"
        payload = {"job_url": job_url}

        try:
            logger.info(f"Calling perf-keeper: {endpoint}")
            logger.debug(f"Request payload: {payload}")

            response = self.client.post(endpoint, json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Perf-keeper analysis complete: "
                f"passed={result.get('passed')}, "
                f"duration={result.get('analysis_duration_seconds')}s"
            )

            return result

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

    def close(self):
        """Close HTTP client"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

**Key Features**:
- Uses `httpx` for modern HTTP client with retries
- Configurable timeout (default 120s for AI analysis)
- Optional API token support
- Comprehensive error handling
- Graceful degradation (returns None on failure)
- Context manager support

---

### Step 2: Add JIRA Attachment Method

**File**: `firstpass/jira_client.py`

**Modify**: Add new method to existing `JiraClient` class.

**Add this method** (after the `add_comment` method, around line 194):

```python
    def add_attachment(self, issue: Issue, filename: str, content: str):
        """Add text file attachment to issue

        Args:
            issue: JIRA issue
            filename: Attachment filename (e.g., "analysis.md")
            content: File content as string
        """
        try:
            # Create in-memory file
            from io import BytesIO

            file_obj = BytesIO(content.encode("utf-8"))
            file_obj.name = filename

            # Upload attachment
            self.jira.add_attachment(issue=issue, attachment=file_obj, filename=filename)
            logger.info(f"Added attachment '{filename}' ({len(content)} bytes) to {issue.key}")

        except Exception as e:
            logger.error(f"Failed to add attachment to {issue.key}: {e}", exc_info=True)
            raise
```

**Why BytesIO?**
- JIRA Python library expects a file-like object
- BytesIO creates an in-memory file from string content
- Avoids writing temporary files to disk

---

### Step 3: Extract Prow Job URL

**File**: `firstpass/release_controller.py`

**Modify**: Add new method to existing `ReleaseControllerClient` class.

**Add this method** (after the `extract_build_url_from_description` method, around line 181):

```python
    def extract_prow_job_url(self, description: str) -> Optional[str]:
        """Extract Prow job URL from JIRA description

        Args:
            description: JIRA issue description

        Returns:
            Prow job URL or None
            Example: "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{job}/{id}"
        """
        if not description:
            return None

        # Pattern: Look for Prow URL
        # Example: https://prow.ci.openshift.org/view/gs/origin-ci-test/logs/periodic-ci-.../2053857063406145536
        prow_pattern = r"(https://prow\.ci\.openshift\.org/view/gs/[^\s\]\)\>]+)"

        match = re.search(prow_pattern, description)
        if match:
            url = match.group(1)
            logger.info(f"Extracted Prow job URL: {url}")
            return url

        logger.warning("Could not extract Prow job URL from description")
        return None
```

**Note**: This is similar to `extract_build_url_from_description()` but returns the Prow URL itself, not the converted GCS build-log.txt URL.

---

### Step 4: Update Phase Base Class

**File**: `firstpass/phases/base.py`

**Modify**: Update `__init__` method to accept `perf_keeper_client` parameter.

**Change this** (line 15-31):

```python
    def __init__(
        self, config, jira_client, release_controller_client, phase_name: str, dry_run: bool = False
    ):
```

**To this**:

```python
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
        self.perf_keeper_client = perf_keeper_client  # NEW
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
```

---

### Step 5: Update Framework to Initialize PerfKeeperClient

**File**: `firstpass/framework.py`

**Modify**: Add perf-keeper client initialization and pass to phases.

**Step 5.1**: Add import at top of file (around line 4):

```python
from .perf_keeper_client import PerfKeeperClient
```

**Step 5.2**: Add instance variable in `__init__` (after line 42):

```python
    def __init__(self, config_path: str = "config.yaml", dry_run: bool = False):
        # ... existing code ...
        
        # Initialize clients
        self.jira_client = self._init_jira_client()
        self.release_controller_client = self._init_release_controller_client()
        self.perf_keeper_client = self._init_perf_keeper_client()  # NEW

        # Initialize phases
        self.phases = self._init_phases()
```

**Step 5.3**: Add initialization method (after `_init_release_controller_client`, around line 79):

```python
    def _init_perf_keeper_client(self) -> Optional[PerfKeeperClient]:
        """Initialize Perf-Keeper client

        Returns:
            PerfKeeperClient instance or None if not configured
        """
        base_url = self.config.get("perf_keeper.base_url")

        if not base_url:
            logger.info("Perf-keeper not configured - skipping initialization")
            return None

        timeout = self.config.get("perf_keeper.timeout", 120)
        api_token = self.config.get("perf_keeper.api_token")

        try:
            return PerfKeeperClient(base_url=base_url, timeout=timeout, api_token=api_token)
        except Exception as e:
            logger.warning(f"Failed to initialize perf-keeper client: {e}")
            return None
```

**Step 5.4**: Pass to phases (modify `_init_phases`, around line 92):

```python
    def _init_phases(self) -> Dict[str, Phase]:
        """Initialize enabled phases

        Returns:
            Dictionary of phase name to phase instance
        """
        phases = {}
        enabled_phases = self.config.enabled_phases

        for phase_name in enabled_phases:
            if phase_name in self.PHASE_REGISTRY:
                phase_class = self.PHASE_REGISTRY[phase_name]
                phases[phase_name] = phase_class(
                    self.config,
                    self.jira_client,
                    self.release_controller_client,
                    phase_name,
                    dry_run=self.dry_run,
                    perf_keeper_client=self.perf_keeper_client,  # NEW
                )
                logger.info(f"Initialized {phase_name}")
            else:
                logger.warning(f"Phase '{phase_name}' not found in registry")

        return phases
```

---

### Step 6: Update Phase1 to Call Perf-Keeper

**File**: `firstpass/phases/phase1.py`

**Modify**: Update the "accepted" branch in `process_issue()` method.

**Find this section** (around line 149-171):

```python
        elif phase_lower == "accepted":
            label = self.get_phase_config("label", "phase1_done")
            self.logger.info(
                f"{issue.key}: Payload {payload_tag} was ACCEPTED - advancing to Phase 2"
            )

            if self.dry_run:
                self.logger.warning(
                    f"[DRY RUN] Would add comment to {issue.key}: "
                    f"Payload {payload_tag} was accepted by Release Controller. "
                    f"Stream: {stream}, Phase: {phase}. Moving to Phase 2 for analysis."
                )
                self.logger.warning(f"[DRY RUN] Would add label '{label}' to {issue.key}")
            else:
                self.jira_client.add_comment(
                    issue,
                    f"Payload {payload_tag} was accepted by Release Controller. "
                    f"Stream: {stream}, Phase: {phase}. Moving to Phase 2 for analysis.",
                )
                self.jira_client.add_label(issue, label)
            return True
```

**Replace with**:

```python
        elif phase_lower == "accepted":
            label = self.get_phase_config("label", "phase1_done")
            self.logger.info(
                f"{issue.key}: Payload {payload_tag} was ACCEPTED - advancing to Phase 2"
            )

            # NEW: Generate analysis report via perf-keeper
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
                            report_size = len(markdown_report)

                            if self.dry_run:
                                # Preview first 500 chars
                                preview = (
                                    markdown_report[:500] + "..."
                                    if len(markdown_report) > 500
                                    else markdown_report
                                )
                                self.logger.warning(
                                    f"[DRY RUN] Would attach '{filename}' ({report_size} bytes) to {issue.key}"
                                )
                                self.logger.info(f"Report preview:\n{preview}")
                            else:
                                # Upload attachment
                                try:
                                    self.jira_client.add_attachment(issue, filename, markdown_report)
                                    self.logger.info(
                                        f"{issue.key}: Attached analysis report ({report_size} bytes)"
                                    )
                                except Exception as e:
                                    self.logger.error(
                                        f"{issue.key}: Failed to attach report: {e}"
                                    )
                        else:
                            self.logger.warning(
                                f"{issue.key}: Perf-keeper returned empty analysis"
                            )
                    elif analysis_result and analysis_result.get("passed"):
                        self.logger.info(
                            f"{issue.key}: Job actually passed - skipping analysis attachment"
                        )
                    else:
                        self.logger.warning(
                            f"{issue.key}: Perf-keeper analysis failed - continuing without report"
                        )
                else:
                    self.logger.warning(
                        f"{issue.key}: Could not extract Prow URL - skipping perf-keeper analysis"
                    )
            else:
                self.logger.info(
                    f"{issue.key}: Perf-keeper not configured - skipping analysis"
                )

            # Existing comment and label logic
            if self.dry_run:
                self.logger.warning(
                    f"[DRY RUN] Would add comment to {issue.key}: "
                    f"Payload {payload_tag} was accepted by Release Controller. "
                    f"Stream: {stream}, Phase: {phase}. Moving to Phase 2 for analysis."
                )
                self.logger.warning(f"[DRY RUN] Would add label '{label}' to {issue.key}")
            else:
                comment_text = (
                    f"Payload {payload_tag} was accepted by Release Controller. "
                    f"Stream: {stream}, Phase: {phase}. Moving to Phase 2 for analysis."
                )
                if markdown_report:
                    comment_text += "\n\nRegression analysis report has been attached."

                self.jira_client.add_comment(issue, comment_text)
                self.jira_client.add_label(issue, label)

            return True
```

**Key Points**:
- Only calls perf-keeper if client is configured
- Only attaches report if job actually failed (`passed=false`)
- Graceful degradation on errors
- Dry-run shows preview of report
- Updates comment to mention attachment

---

### Step 7: Update Configuration

**File**: `config.yaml`

**Add** this section (after the `gcs` section, around line 12):

```yaml
perf_keeper:
  base_url: "http://localhost:8080"  # Update to actual deployment URL
  timeout: 120  # Analysis timeout in seconds
  # api_token: "your-token-here"  # Optional: uncomment if authentication required
```

**Full context**:

```yaml
# FirstPass Agent Configuration

jira:
  server: "https://redhat.atlassian.net"
  project: "PERFSCALE"
  component: "CPT_ISSUES"

release_controller:
  base_url: "https://amd64.ocp.releases.ci.openshift.org/api/v1"

gcs:
  base_url: "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs"

perf_keeper:
  base_url: "http://localhost:8080"
  timeout: 120

phases:
  enabled:
    - phase1

  phase1:
    status: "New"
    transition_done: "Done"
    label: "phase1_done"

  phase2:
    status: "In Progress"
    label_required: "phase1_done"
    label: "phase2_done"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

### Step 8: Update Dependencies

**File**: `requirements.txt`

**Check if `httpx` is already listed**. If not, add:

```
httpx>=0.27.0
```

**Install dependencies**:

```bash
source .venv/bin/activate
uv pip install httpx>=0.27.0
```

---

## Testing Guide

### Test 1: Dry-Run with Local Perf-Keeper

**Prerequisites**:
1. Perf-keeper running locally on `http://localhost:8080`
2. JIRA credentials configured in `.env`
3. At least one "New" issue in JIRA with accepted payload

**Steps**:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run Phase1 in dry-run mode
python main.py --phase phase1 --dry-run

# Expected output:
# - Phase1 processes issues
# - Logs show "[DRY RUN] Would attach 'regression-analysis-PERFSCALE-XXX.md'"
# - Preview of markdown report displayed
# - No actual JIRA changes made
```

**Verify**:
- Log shows perf-keeper was called
- Report preview contains markdown with sections: Analysis summary, Root cause, Suspect changes, Classification
- No errors in logs

---

### Test 2: Real Execution with Test Issue

**Prerequisites**:
1. Perf-keeper running and accessible
2. Test JIRA issue in "New" status with accepted payload

**Steps**:

```bash
# Run Phase1 (no dry-run flag)
python main.py --phase phase1

# Expected:
# - Issue processed
# - Perf-keeper called
# - Markdown file attached to JIRA
# - Comment added
# - Label "phase1_done" added
```

**Verify in JIRA**:
1. Open the processed issue
2. Check "Attachments" section for `regression-analysis-{ISSUE-KEY}.md`
3. Download and verify markdown format
4. Check comment mentions "analysis report has been attached"
5. Verify label "phase1_done" was added

---

### Test 3: Error Handling

**Test 3.1: Perf-Keeper Unavailable**

```bash
# Stop perf-keeper or use invalid URL
# Edit config.yaml: base_url: "http://localhost:9999"

python main.py --phase phase1

# Expected:
# - Warning: "Perf-keeper request error"
# - Phase1 continues without attachment
# - Comment and label still added
# - No failure/crash
```

**Test 3.2: No Prow URL in Description**

Create a test issue without Prow URL in description.

```bash
python main.py --phase phase1

# Expected:
# - Warning: "Could not extract Prow URL"
# - Phase1 continues without perf-keeper call
# - Comment and label still added
```

**Test 3.3: Perf-Keeper Timeout**

```bash
# Edit config.yaml: timeout: 5

python main.py --phase phase1

# Expected:
# - Error: "Perf-keeper request timed out after 5s"
# - Phase1 continues gracefully
```

---

### Test 4: Code Quality

```bash
# Format code
ruff format firstpass/perf_keeper_client.py

# Check linting
ruff check firstpass/perf_keeper_client.py
ruff check firstpass/jira_client.py
ruff check firstpass/phases/phase1.py

# Type check
ty check firstpass/perf_keeper_client.py
ty check firstpass/jira_client.py
```

---

## Configuration Options

### Deployment Scenarios

#### Local Development

```yaml
perf_keeper:
  base_url: "http://localhost:8080"
  timeout: 120
```

#### OpenShift Internal Service

```yaml
perf_keeper:
  base_url: "http://perf-keeper-service:8080"
  timeout: 180
```

#### External URL with Authentication

```yaml
perf_keeper:
  base_url: "https://perf-keeper.example.com"
  timeout: 180
  api_token: "${PERF_KEEPER_TOKEN}"  # Read from environment variable
```

#### Disabled (for rollback)

```yaml
perf_keeper:
  # base_url: ""  # Comment out or leave empty to disable
```

---

## Error Handling Matrix

| Scenario | Behavior | Impact on Phase1 |
|----------|----------|------------------|
| Perf-keeper not configured | Skip analysis, log info | ✅ Continues normally |
| Perf-keeper unreachable | Log warning, skip attachment | ✅ Continues normally |
| Perf-keeper timeout | Log error, skip attachment | ✅ Continues normally |
| Perf-keeper returns error | Log error, skip attachment | ✅ Continues normally |
| No Prow URL in description | Log warning, skip analysis | ✅ Continues normally |
| JIRA attachment upload fails | Log error, continue | ✅ Comment/label still added |
| Job actually passed | Log info, skip attachment | ✅ Continues normally |

**Design Principle**: Perf-keeper integration should **never cause Phase1 to fail**. It's an enhancement, not a requirement.

---

## Rollback Plan

If issues arise, rollback is straightforward:

### Option 1: Disable in Config

```yaml
perf_keeper:
  # base_url: ""  # Comment out
```

Restart FirstPass. No code changes needed.

### Option 2: Git Revert

```bash
git log --oneline  # Find commit hash
git revert <commit-hash>
git push
```

### Option 3: Manual Cleanup

If attachments need to be removed from JIRA:
1. Manually delete attachments from affected issues
2. No database changes needed

---

## Monitoring & Observability

### Log Messages to Watch

**Success**:
```
INFO - Calling perf-keeper: http://localhost:8080/analyze
INFO - Perf-keeper analysis complete: passed=False, duration=45s
INFO - PERFSCALE-123: Attached analysis report (15234 bytes)
```

**Warnings** (non-fatal):
```
WARNING - Perf-keeper not configured - skipping initialization
WARNING - Could not extract Prow URL - skipping perf-keeper analysis
WARNING - Perf-keeper analysis failed - continuing without report
```

**Errors** (handled gracefully):
```
ERROR - Perf-keeper HTTP error: 500 - Internal Server Error
ERROR - Perf-keeper request timed out after 120s
ERROR - Failed to attach report: JIRA API error
```

### Metrics to Track

1. **Success rate**: % of issues with successful attachment
2. **Analysis duration**: Time taken by perf-keeper (from response)
3. **Error rate**: % of perf-keeper calls that fail
4. **Attachment size**: Size of markdown reports

---

## Troubleshooting

### Issue: Perf-keeper not called

**Check**:
1. Is `base_url` configured in `config.yaml`?
2. Is perf-keeper client initialized? (Check logs for "Initialized PerfKeeperClient")
3. Is the issue in "accepted" phase? (Perf-keeper only called for accepted payloads)

### Issue: "Could not extract Prow URL"

**Check**:
1. Does JIRA description contain Prow URL?
2. URL format: `https://prow.ci.openshift.org/view/gs/...`
3. Check regex pattern in `extract_prow_job_url()`

### Issue: Attachment not visible in JIRA

**Check**:
1. JIRA permissions - does API user have permission to add attachments?
2. Check JIRA audit log for attachment upload event
3. Verify no exceptions in logs during `add_attachment()`

### Issue: Perf-keeper times out

**Solutions**:
1. Increase timeout in config: `timeout: 300`
2. Check perf-keeper logs for slow LLM responses
3. Verify network connectivity

---

## Future Enhancements

### Phase 2 Integration

Once Phase1 is stable, Phase2 can:
1. Read the attached markdown report
2. Parse structured data (regressing version, suspect PRs)
3. Perform additional analysis or escalation

### Metrics Dashboard

Track:
- Number of reports generated per day
- Average analysis duration
- Most common classifications
- Success/failure rates

### Report Templates

Customize markdown output format based on:
- Test type (orion, kube-burner, etc.)
- Severity level
- Payload version

---

## Acceptance Criteria Checklist

- [ ] FirstPass calls perf-keeper `/analyze` endpoint with Prow job URL
- [ ] Markdown analysis report generated by perf-keeper
- [ ] Report contains: regression data from Orion, payload info from Sippy, Release Controller data
- [ ] Report uploaded as JIRA attachment
- [ ] Attachment available for Phase2 analysis
- [ ] Dry-run mode works correctly (preview without upload)
- [ ] Error handling graceful (Phase1 never fails due to perf-keeper)
- [ ] Code passes: ruff format, ruff check, ty check
- [ ] Documentation complete
- [ ] Testing guide validated

---

## Summary

This implementation adds perf-keeper integration to FirstPass Phase1 with:
- ✅ Minimal changes to existing code
- ✅ Graceful degradation on errors
- ✅ Dry-run support for testing
- ✅ Comprehensive logging
- ✅ Easy rollback
- ✅ No breaking changes

The integration is **optional** and **fail-safe** - FirstPass continues to work even if perf-keeper is unavailable.
