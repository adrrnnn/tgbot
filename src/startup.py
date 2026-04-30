"""
Application startup and initialization orchestration.

Handles dependency checking, database setup, configuration loading,
and pre-flight checks before launching the main application.

Based on PLAN 1: Startup Flow & Dependency Management
"""

import sys
import logging
import subprocess
import importlib.util
from typing import Dict, List, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DependencyChecker:
    """Check and install required Python packages."""
    
    # Required packages with minimum versions
    REQUIRED_PACKAGES = {
        "pyrogram": "2.0.106",
        "PyQt5": "5.15.0",
        "cryptography": "41.0.0",
    }
    
    @staticmethod
    def check_package(package_name: str) -> bool:
        """
        Check if a package is installed using importlib.
        
        Args:
            package_name: Python package name to check
            
        Returns:
            bool: True if installed, False otherwise
        """
        spec = importlib.util.find_spec(package_name)
        return spec is not None
    
    @classmethod
    def check_all_dependencies(cls) -> Tuple[bool, List[str]]:
        """
        Check if all required packages are installed.
        
        Returns:
            Tuple of (all_installed: bool, missing_packages: List[str])
        """
        missing = []
        
        for package_name in cls.REQUIRED_PACKAGES.keys():
            if not cls.check_package(package_name):
                missing.append(package_name)
                logger.warning(f"Missing package: {package_name}")
        
        if missing:
            logger.error(f"Missing {len(missing)} required packages")
            return False, missing
        else:
            logger.info("[OK] All dependencies installed")
            return True, []
    
    @staticmethod
    def install_dependencies(packages: List[str], max_retries: int = 3) -> bool:
        """
        Install missing packages using pip.
        
        Args:
            packages: List of package names to install
            max_retries: Maximum retry attempts
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not packages:
            return True
        
        logger.info(f"Installing {len(packages)} packages...")
        
        for attempt in range(max_retries):
            try:
                # Use subprocess to call pip
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + packages,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    logger.info("[OK] Packages installed successfully")
                    return True
                else:
                    logger.warning(f"Installation attempt {attempt + 1} failed")
                    if "Permission" in result.stderr:
                        logger.error("Permission denied. Try with admin/sudo")
                        return False
            
            except subprocess.TimeoutExpired:
                logger.warning(f"Installation timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    logger.info("Retrying...")
            
            except Exception as e:
                logger.error(f"Installation failed: {e}")
                return False
        
        logger.error("Installation failed after all retries")
        return False


class StartupOrchestrator:
    """Orchestrate application startup sequence."""
    
    def __init__(self):
        """Initialize startup orchestrator."""
        self.project_root = Path(__file__).parent.parent
        self.passed_checks = []
        self.failed_checks = []
    
    def run_startup_sequence(self) -> bool:
        """
        Execute complete startup sequence.
        
        Returns:
            bool: True if all checks passed, False otherwise
        """
        logger.info("=" * 60)
        logger.info("TELEGRAM BOT - STARTUP SEQUENCE")
        logger.info("=" * 60)
        
        # Phase 1: Check dependencies
        logger.info("\n[Phase 1/4] Checking dependencies...")
        if not self._phase_check_dependencies():
            return False
        
        # Phase 2: Initialize database
        logger.info("\n[Phase 2/4] Initializing database...")
        if not self._phase_initialize_database():
            return False
        
        # Phase 3: Load configuration
        logger.info("\n[Phase 3/4] Loading configuration...")
        if not self._phase_load_configuration():
            return False
        
        # Phase 4: Pre-flight checks
        logger.info("\n[Phase 4/4] Running pre-flight checks...")
        if not self._phase_preflight_checks():
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("[OK] STARTUP SEQUENCE COMPLETED SUCCESSFULLY")
        logger.info("=" * 60 + "\n")
        return True
    
    def _phase_check_dependencies(self) -> bool:
        """Phase 1: Check and install dependencies."""
        all_installed, missing = DependencyChecker.check_all_dependencies()
        
        if not all_installed:
            logger.info(f"Missing packages: {', '.join(missing)}")
            
            # Try automatic installation
            if DependencyChecker.install_dependencies(missing):
                logger.info("[OK] Dependencies installed")
                self.passed_checks.append("Dependencies installed")
                return True
            else:
                logger.error("Failed to install dependencies")
                logger.info("Run manually: pip install -r requirements.txt")
                self.failed_checks.append("Dependency installation failed")
                return False
        
        self.passed_checks.append("All dependencies present")
        return True
    
    def _phase_initialize_database(self) -> bool:
        """Phase 2: Initialize database schema."""
        try:
            # Import here to ensure dependencies are installed
            from src.database import initialize_database_with_defaults
            
            success = initialize_database_with_defaults(
                db_path=str(self.project_root / "telegrambot.db")
            )
            
            if success:
                self.passed_checks.append("Database initialized")
                return True
            else:
                self.failed_checks.append("Database initialization failed")
                return False
        
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            self.failed_checks.append(f"Database error: {e}")
            return False
    
    def _phase_load_configuration(self) -> bool:
        """Phase 3: Load application configuration."""
        try:
            from src.config import get_config
            
            config = get_config()
            
            # Check if config has been set up
            if not config.telegram:
                logger.warning("⚠️  Telegram credentials not configured")
                logger.info("Run: python -m src.config")
                logger.info("Or set environment variables:")
                logger.info("  - TELEGRAM_API_ID")
                logger.info("  - TELEGRAM_API_HASH")
                logger.info("  - TELEGRAM_PHONE (optional)")
                
                # This is not fatal; user can set up later
                self.passed_checks.append("Configuration loaded (credentials pending)")
                return True
            
            if not config.validate():
                logger.error("Configuration validation failed")
                self.failed_checks.append("Configuration invalid")
                return False
            
            self.passed_checks.append("Configuration valid")
            return True
        
        except Exception as e:
            logger.error(f"Configuration loading error: {e}")
            self.failed_checks.append(f"Config error: {e}")
            return False
    
    def _phase_preflight_checks(self) -> bool:
        """Phase 4: Run pre-flight checks."""
        checks_passed = 0
        checks_total = 0
        
        # Check project structure
        checks_total += 1
        required_dirs = ["src", "config", "logs", "pyrogram_sessions"]
        missing_dirs = [d for d in required_dirs if not (self.project_root / d).exists()]
        
        if not missing_dirs:
            logger.info("  [OK] Project directories present")
            checks_passed += 1
        else:
            logger.warning(f"  ⚠️  Missing directories: {', '.join(missing_dirs)}")
        
        # Check database file
        checks_total += 1
        db_path = self.project_root / "telegrambot.db"
        if db_path.exists():
            logger.info("  [OK] Database file present")
            checks_passed += 1
        else:
            logger.warning("  ⚠️  Database file not found (will be created on first run)")
        
        logger.info(f"  Pre-flight checks: {checks_passed}/{checks_total} passed")
        self.passed_checks.append(f"Pre-flight checks: {checks_passed}/{checks_total}")
        
        return True
    
    def get_status(self) -> Dict[str, any]:
        """Get startup status summary."""
        return {
            "passed": len(self.passed_checks),
            "failed": len(self.failed_checks),
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
        }


def main():
    """Main startup entry point."""
    orchestrator = StartupOrchestrator()
    success = orchestrator.run_startup_sequence()
    
    status = orchestrator.get_status()
    print("\nStartup Status:")
    print(f"  Passed: {status['passed']}")
    print(f"  Failed: {status['failed']}")
    
    if status['failed_checks']:
        print("\nFailed checks:")
        for check in status['failed_checks']:
            print(f"  [ERROR] {check}")
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
