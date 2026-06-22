"""Core framework for FirstPass Agent"""

import logging
from typing import Dict, Optional, Type

from .config import Config
from .jira_client import JiraClient
from .perf_keeper_client import PerfKeeperClient
from .phases.base import Phase
from .phases.phase1 import Phase1
from .phases.phase2 import Phase2
from .release_controller import ReleaseControllerClient
from .report import RegressionReport

logger = logging.getLogger(__name__)


class FirstPassFramework:
    """Main framework orchestrating all phases"""

    # Registry of available phases
    PHASE_REGISTRY: Dict[str, Type[Phase]] = {
        "phase1": Phase1,
        "phase2": Phase2,
    }

    def __init__(self, config_path: str = "config.yaml", dry_run: bool = False):
        """Initialize framework

        Args:
            config_path: Path to configuration file
            dry_run: If True, no JIRA updates will be made
        """
        self.config = Config(config_path)
        self.dry_run = dry_run
        self._setup_logging()

        if self.dry_run:
            logger.warning("DRY RUN MODE - No JIRA updates will be made")

        # Initialize clients
        self.jira_client = self._init_jira_client()
        self.release_controller_client = self._init_release_controller_client()
        self.perf_keeper_client = self._init_perf_keeper_client()

        # Initialize phases
        self.phases = self._init_phases()

    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = self.config.get("logging.level", "INFO")
        log_format = self.config.get(
            "logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        logging.basicConfig(level=getattr(logging, log_level), format=log_format)

    def _init_jira_client(self) -> JiraClient:
        """Initialize JIRA client

        Returns:
            JiraClient instance
        """
        return JiraClient(
            server=self.config.jira_server,
            email=self.config.jira_email,
            api_token=self.config.jira_api_token,
            username=self.config.jira_username,
            password=self.config.jira_password,
        )

    def _init_release_controller_client(self) -> ReleaseControllerClient:
        """Initialize Release Controller client

        Returns:
            ReleaseControllerClient instance
        """
        return ReleaseControllerClient(
            base_url=self.config.release_controller_url, gcs_base_url=self.config.gcs_base_url
        )

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

        return PerfKeeperClient(base_url=base_url, timeout=timeout, api_token=api_token)

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
                    perf_keeper_client=self.perf_keeper_client,
                )
                logger.info(f"Initialized {phase_name}")
            else:
                logger.warning(f"Phase '{phase_name}' not found in registry")

        return phases

    def run_phase(self, phase_name: str):
        """Run a specific phase

        Args:
            phase_name: Name of phase to run
        """
        if phase_name not in self.phases:
            logger.error(f"Phase '{phase_name}' not enabled or not found")
            return

        phase = self.phases[phase_name]
        phase.run()

    def run_all_phases(self):
        """Run all enabled phases in order"""
        logger.info("Running all enabled phases")

        for phase_name, phase in self.phases.items():
            logger.info(f"=== Running {phase_name} ===")
            phase.run()

    def run(self, phase: Optional[str] = None):
        """Run the framework

        Args:
            phase: Specific phase to run (optional). If None, runs all phases.
        """
        logger.info("FirstPass Agent starting")

        if phase:
            self.run_phase(phase)
        else:
            self.run_all_phases()

        logger.info("FirstPass Agent complete")

    def cleanup(self):
        """Clean up resources"""
        if self.perf_keeper_client:
            self.perf_keeper_client.close()

    def generate_report(self):
        """Generate and display regression report"""
        logger.info("Generating regression report")

        reporter = RegressionReport(
            jira_client=self.jira_client,
            project=self.config.jira_project,
            component=self.config.jira_component,
        )

        report = reporter.generate_report()
        print(report)
