"""Tests for FirstPassFramework"""

from unittest.mock import Mock, patch

from firstpass.framework import FirstPassFramework


class TestFirstPassFramework:
    """Test FirstPassFramework class"""

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_framework_initialization(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test framework initializes correctly"""
        framework = FirstPassFramework(str(sample_config_file))

        assert framework.config is not None
        assert framework.jira_client is not None
        assert framework.release_controller_client is not None
        assert framework.perf_keeper_client is not None
        assert isinstance(framework.phases, dict)
        assert framework.dry_run is False

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_phase_registry(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test phase registry contains expected phases"""
        assert "phase1" in FirstPassFramework.PHASE_REGISTRY
        assert "phase2" in FirstPassFramework.PHASE_REGISTRY

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_enabled_phases_initialization(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test that enabled phases are initialized"""
        framework = FirstPassFramework(str(sample_config_file))

        enabled_phases = framework.config.enabled_phases
        for phase_name in enabled_phases:
            assert phase_name in framework.phases

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_jira_client_initialization(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test JIRA client is initialized with correct parameters"""
        _ = FirstPassFramework(str(sample_config_file))

        mock_jira_client.assert_called_once()
        call_kwargs = mock_jira_client.call_args.kwargs

        assert call_kwargs["server"] == "https://test.atlassian.net"
        assert call_kwargs["email"] == "test@example.com"
        assert call_kwargs["api_token"] == "test-token-123"

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_release_controller_initialization(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test Release Controller client is initialized with correct parameters"""
        _ = FirstPassFramework(str(sample_config_file))

        mock_rc_client.assert_called_once()
        call_kwargs = mock_rc_client.call_args.kwargs

        assert call_kwargs["base_url"] == "https://test-release-controller.example.com"
        assert call_kwargs["gcs_base_url"] == "https://storage.googleapis.com/test-bucket"

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_perf_keeper_initialization(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test Perf-Keeper client is initialized when configured"""
        framework = FirstPassFramework(str(sample_config_file))

        mock_perf_keeper_client.assert_called_once()
        assert framework.perf_keeper_client is not None

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_run_specific_phase(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test running a specific phase"""
        framework = FirstPassFramework(str(sample_config_file))

        for phase in framework.phases.values():
            phase.run = Mock()

        framework.run_phase("phase1")

        framework.phases["phase1"].run.assert_called_once()

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_run_all_phases(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test running all phases"""
        framework = FirstPassFramework(str(sample_config_file))

        for phase in framework.phases.values():
            phase.run = Mock()

        framework.run_all_phases()

        for phase in framework.phases.values():
            phase.run.assert_called_once()

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_run_with_specific_phase(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test run method with specific phase"""
        framework = FirstPassFramework(str(sample_config_file))

        framework.phases["phase1"].run = Mock()

        framework.run(phase="phase1")

        framework.phases["phase1"].run.assert_called_once()

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_run_without_phase(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test run method without specifying phase (runs all)"""
        framework = FirstPassFramework(str(sample_config_file))

        for phase in framework.phases.values():
            phase.run = Mock()

        framework.run()

        for phase in framework.phases.values():
            phase.run.assert_called_once()

    @patch("firstpass.framework.PerfKeeperClient")
    @patch("firstpass.framework.ReleaseControllerClient")
    @patch("firstpass.framework.JiraClient")
    def test_phases_receive_perf_keeper_client(
        self,
        mock_jira_client,
        mock_rc_client,
        mock_perf_keeper_client,
        sample_config_file,
        mock_env_vars,
    ):
        """Test that phases are initialized with perf_keeper_client"""
        framework = FirstPassFramework(str(sample_config_file))

        for phase in framework.phases.values():
            assert hasattr(phase, "perf_keeper_client")
            assert phase.perf_keeper_client is not None
