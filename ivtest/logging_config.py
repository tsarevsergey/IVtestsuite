"""
Centralized logging configuration for IV Test Software.
Provides file + console logging with consistent format.
"""
import logging
import os
from datetime import datetime

def setup_logging(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """
    Configure centralized logging with file and console handlers.
    
    Args:
        log_dir: Directory for log files
        level: Logging level (default INFO)
    
    Returns:
        Root logger configured for the application
    """
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"ivtest_{timestamp}.log")
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # Capture everything to file
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger("ivtest")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    root_logger.info(f"Logging initialized. File: {log_file}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"ivtest.{name}")


class EndpointFilter(logging.Filter):
    """
    Filter out access logs for specific endpoints (e.g. status polling).
    """
    def __init__(self, *paths):
        super().__init__()
        self.paths = paths

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(path in msg for path in self.paths)
