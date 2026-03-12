# utils/logging_config.py

import logging
import sys
from pathlib import Path
from typing import Dict


class KiwisinoLoggerManager:
    """Singleton logger manager for the Kiwisino cog.

    Separate from the fishing cog's LoggerManager so both cogs can be
    loaded simultaneously without handler collisions.
    """
    _instance = None
    _loggers: Dict[str, logging.Logger] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KiwisinoLoggerManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.log_dir = Path(__file__).parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)

        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        self._file_handler = logging.FileHandler(
            self.log_dir / "kiwisino.log",
            encoding='utf-8'
        )
        self._file_handler.setFormatter(self.formatter)

        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setFormatter(self.formatter)

    def get_logger(self, module_name: str) -> logging.Logger:
        if module_name not in self._loggers:
            logger = logging.getLogger(f'kiwisino.{module_name}')
            logger.setLevel(logging.DEBUG)
            logger.handlers.clear()
            logger.addHandler(self._file_handler)
            logger.addHandler(self._console_handler)
            self._loggers[module_name] = logger
        return self._loggers[module_name]

    @classmethod
    def reset(cls):
        """Reset the singleton — call on cog unload to avoid stale state."""
        if cls._instance is not None:
            for logger in cls._instance._loggers.values():
                logger.handlers.clear()
            cls._instance._loggers.clear()
            cls._instance = None


logger_manager = KiwisinoLoggerManager()


def get_logger(module_name: str) -> logging.Logger:
    return logger_manager.get_logger(module_name)
