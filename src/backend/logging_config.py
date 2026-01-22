"""
Production-ready logging configuration for Tata Play application.
Supports structured logging, log rotation, and multiple output formats.
"""
import logging
import logging.handlers
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
import os


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
            
        # Add request context if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_email"):
            log_data["user_email"] = record.user_email
        if hasattr(record, "endpoint"):
            log_data["endpoint"] = record.endpoint
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration"):
            log_data["duration"] = record.duration
            
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    environment: str = "development",
    log_level: str = "INFO",
    log_dir: str = "logs",
    app_name: str = "tataplay"
) -> None:
    """
    Setup production-ready logging configuration.
    
    Args:
        environment: Environment name (development/production)
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR)
        log_dir: Directory for log files
        app_name: Application name for log files
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console Handler - Always enabled
    console_handler = logging.StreamHandler(sys.stdout)
    if environment == "development":
        # Use colored formatter in development
        console_format = ColoredFormatter(
            fmt='%(asctime)s | %(levelname)s | [%(request_id)s] | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            defaults={'request_id': '-'}
        )
    else:
        # Use simple formatter in production
        console_format = logging.Formatter(
            fmt='%(asctime)s | %(levelname)s | [%(request_id)s] | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            defaults={'request_id': '-'}
        )
    console_handler.setFormatter(console_format)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    # File Handler - Rotating JSON logs for production
    app_log_file = log_path / f"{app_name}_app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=app_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    if environment == "production":
        # JSON format for production (easier to parse)
        file_handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format for development
        file_format = logging.Formatter(
            fmt='%(asctime)s | %(levelname)s | [%(request_id)s] | %(process)d | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            defaults={'request_id': '-'}
        )
        file_handler.setFormatter(file_format)
    file_handler.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    
    # Error File Handler - Separate file for errors only
    error_log_file = log_path / f"{app_name}_error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        filename=error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    if environment == "production":
        error_handler.setFormatter(JSONFormatter())
    else:
        error_format = logging.Formatter(
            fmt='%(asctime)s | %(levelname)s | [%(request_id)s] | %(process)d | %(name)s:%(funcName)s:%(lineno)d | %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            defaults={'request_id': '-'}
        )
        error_handler.setFormatter(error_format)
    root_logger.addHandler(error_handler)
    
    # Access Log Handler - Separate file for HTTP requests
    access_log_file = log_path / f"{app_name}_access.log"
    access_handler = logging.handlers.RotatingFileHandler(
        filename=access_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    access_handler.setLevel(logging.INFO)
    if environment == "production":
        access_handler.setFormatter(JSONFormatter())
    else:
        access_handler.setFormatter(file_format)
    
    # Create separate logger for access logs
    access_logger = logging.getLogger("access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    # Clear any existing handlers to prevent duplicates
    access_logger.handlers.clear()
    access_logger.addHandler(access_handler)
    # Also log to console in development with a separate handler
    if environment == "development":
        access_console_handler = logging.StreamHandler(sys.stdout)
        access_console_format = ColoredFormatter(
            fmt='%(asctime)s | %(levelname)s | [%(request_id)s] | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            defaults={'request_id': '-'}
        )
        access_console_handler.setFormatter(access_console_format)
        access_console_handler.setLevel(numeric_level)
        access_logger.addHandler(access_console_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
    logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
    
    # Log startup message
    root_logger.info(f"Logging system initialized - Environment: {environment}, Level: {log_level}")
    root_logger.info(f"Log files location: {log_path.absolute()}")
    root_logger.info(f"  - Application logs: {app_log_file}")
    root_logger.info(f"  - Error logs: {error_log_file}")
    root_logger.info(f"  - Access logs: {access_log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context: Any
) -> None:
    """
    Log a message with additional context.
    
    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        message: Log message
        **context: Additional context to log (request_id, user_email, etc.)
    """
    extra = {"extra_data": context}
    # Extract request_id if provided in context
    if "request_id" in context:
        extra["request_id"] = context["request_id"]
    logger.log(level, message, extra=extra)


def log_with_request(
    logger: logging.Logger,
    level: int,
    message: str,
    request_id: str,
    **context: Any
) -> None:
    """
    Log a message with request ID and additional context.
    
    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.ERROR, etc.)
        message: Log message
        request_id: Request ID to track the request
        **context: Additional context to log
    """
    extra = {"request_id": request_id, "extra_data": context}
    # Extract other standard fields
    if "user_email" in context:
        extra["user_email"] = context["user_email"]
    if "endpoint" in context:
        extra["endpoint"] = context["endpoint"]
    if "method" in context:
        extra["method"] = context["method"]
    if "status_code" in context:
        extra["status_code"] = context["status_code"]
    if "duration" in context:
        extra["duration"] = context["duration"]
    logger.log(level, message, extra=extra)
