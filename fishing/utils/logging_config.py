# utils/logging_config.py

import logging
import sys
from pathlib import Path
from typing import Dict


class LoggerManager:
    """Singleton class to manage all loggers in the cog"""
    _instance = None
    _loggers: Dict[str, logging.Logger] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the logging system with a single unified log file"""
        self.log_dir = Path(__file__).parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)

        # Create base formatter — module name is included via %(name)s
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Single file handler shared by all loggers
        self._file_handler = logging.FileHandler(
            self.log_dir / "fishing.log",
            encoding='utf-8'
        )
        self._file_handler.setFormatter(self.formatter)

        # Single console handler shared by all loggers
        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setFormatter(self.formatter)

    def get_logger(self, module_name: str) -> logging.Logger:
        """Get or create a logger for a specific module"""
        if module_name not in self._loggers:
            logger = logging.getLogger(f'fishing.{module_name}')
            logger.setLevel(logging.DEBUG)

            # Remove any existing handlers
            logger.handlers.clear()

            # Attach shared handlers
            logger.addHandler(self._file_handler)
            logger.addHandler(self._console_handler)

            self._loggers[module_name] = logger

        return self._loggers[module_name]

    @classmethod
    def reset(cls):
        """Reset the singleton — call on cog unload to avoid stale state"""
        if cls._instance is not None:
            for logger in cls._instance._loggers.values():
                logger.handlers.clear()
            cls._instance._loggers.clear()
            cls._instance = None


# Create global logger manager instance
logger_manager = LoggerManager()


def get_logger(module_name: str) -> logging.Logger:
    """Convenience function to get a logger"""
    return logger_manager.get_logger(module_name)
