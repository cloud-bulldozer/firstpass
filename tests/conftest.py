"""Pytest configuration and fixtures"""

import pytest


@pytest.fixture
def sample_config_dict():
    """Sample configuration dictionary"""
    return {
        "jira": {
            "server": "https://test.atlassian.net",
            "project": "TEST",
            "component": "TEST_COMPONENT",
        },
        "release_controller": {"base_url": "https://test-release-controller.example.com"},
        "gcs": {"base_url": "https://storage.googleapis.com/test-bucket"},
        "perf_keeper": {"base_url": "http://localhost:8080", "timeout": 120},
        "phases": {"enabled": ["phase1", "phase2"]},
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    }


@pytest.fixture
def sample_config_file(tmp_path, sample_config_dict):
    """Create a temporary config file"""
    import yaml

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config_dict, f)

    return config_file


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables"""
    env_vars = {
        "JIRA_EMAIL": "test@example.com",
        "JIRA_API_TOKEN": "test-token-123",
        "JIRA_USERNAME": "testuser",
        "JIRA_PASSWORD": "testpass",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def clear_env_vars(monkeypatch):
    """Clear JIRA-related environment variables"""
    import os

    for key in ["JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_USERNAME", "JIRA_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)
        # Also ensure the key is not in os.environ
        if key in os.environ:
            monkeypatch.delenv(key, raising=True)
