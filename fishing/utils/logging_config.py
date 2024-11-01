# utils/logging_config.py

import logging
import sys
from pathlib import Path
from typing import Optional, Dict

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
        """Initialize the logging system"""
        self.log_dir = Path(__file__).parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # Create base formatter
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def get_logger(self, module_name: str) -> logging.Logger:
        """Get or create a logger for a specific module"""
        if module_name not in self._loggers:
            # Create new logger
            logger = logging.getLogger(f'fishing.{module_name}')
            logger.setLevel(logging.DEBUG)
            
            # Remove any existing handlers
            logger.handlers.clear()
            
            # Create file handler
            file_handler = logging.FileHandler(
                self.log_dir / f"{module_name}.log",
                encoding='utf-8'
            )
            file_handler.setFormatter(self.formatter)
            logger.addHandler(file_handler)
            
            # Create console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self.formatter)
            logger.addHandler(console_handler)
            
            self._loggers[module_name] = logger
            
        return self._loggers[module_name]

# Create global logger manager instance
logger_manager = LoggerManager()

def get_logger(module_name: str) -> logging.Logger:
    """Convenience function to get a logger"""
    return logger_manager.get_logger(module_name)
