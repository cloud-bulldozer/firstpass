## Type of change

- [ ] Refactor
- [x] New feature
- [ ] Bug fix
- [ ] Optimization
- [ ] Documentation Update

## Description

When Phase1 detects an accepted payload, it extracts the Prow job URL from the JIRA description and calls perf-keeper's `/analyze` endpoint. Perf-keeper performs AI-driven analysis and returns a structured markdown report. Phase1 then uploads this report as a JIRA attachment, providing comprehensive regression analysis data for Phase2 to use.

Specifics:
- `perf_keeper_client.py`: HTTP client for perf-keeper `/analyze` endpoint
- `phase1.py`: Call perf-keeper and attach report in "accepted" branch
- `jira_client.py`: Added `add_attachment()` method to handle files
- `release_controller.py`: Added `extract_prow_job_url()` method to get Prow job url for perf-keeper
- `framework.py`: Added support for perf-keeper
- `base.py`: Added support for perf-keeper
- `config.yaml`: Added perf-keeper configuration

## Checklist before requesting a review

- [x] I have performed a self-review of my code.
- [x] If it is a core feature, I have added thorough tests.

## Testing
**Note:** tests written with Claude code assistance
- All existing tests updated to handle perf-keeper mocking
- Added comprehensive tests for new functionality
- 39 tests passing, 100% coverage on new code

What we tested:
- Client initialization with/without auth
- Successful analysis and report generation
- Error handling (timeout, HTTP errors, network failures)
- JIRA attachment upload
- Framework initialization with perf-keeper
- Dry-run mode