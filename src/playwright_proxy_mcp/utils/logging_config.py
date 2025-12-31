"""
Logging configuration utilities for playwright-proxy-mcp

Provides file-only logging configuration to prevent MCP protocol corruption.
The MCP protocol uses stdout for JSON-RPC communication, so all logging must
go exclusively to files.
"""

import functools
import json
import logging
from pathlib import Path
from typing import Any, Callable, TypeVar


def setup_file_logging(
    log_file: str | Path = "logs/playwright-proxy-mcp.log",
    level: int = logging.INFO,
    format_string: str | None = None,
) -> logging.Logger:
    """
    Configure file-only logging for the application.

    NOTE: We log ONLY to file, NOT to stdout/stderr, because stdout is used
    for MCP protocol communication with the client (FastMCP uses stdio transport).
    Logging to stdout would corrupt the MCP protocol messages.

    Args:
        log_file: Path to the log file (relative or absolute)
        level: Logging level (default: logging.INFO)
        format_string: Custom format string (default: timestamp - name - level - message)

    Returns:
        The root logger instance
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Default format if not provided
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.FileHandler(log_path),
        ],
        force=True,  # Override any existing configuration
    )

    logger = logging.getLogger()
    logger.info(f"Logging configured: file={log_path}, level={logging.getLevelName(level)}")

    # Mute noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_dict(
    logger: logging.Logger, message: str, data: dict[str, Any], level: int = logging.INFO
) -> None:
    """
    Log a dictionary with formatted key-value pairs.

    Args:
        logger: Logger instance
        message: Prefix message
        data: Dictionary to log
        level: Log level (default: INFO)
    """
    logger.log(level, message)
    for key, value in data.items():
        # Mask sensitive values
        if any(sensitive in key.lower() for sensitive in ["token", "password", "secret", "key"]):
            value = "***REDACTED***"
        logger.log(level, f"  {key}: {value}")


# Type variable for the decorator
F = TypeVar("F", bound=Callable[..., Any])


def log_tool_result(logger: logging.Logger | None = None) -> Callable[[F], F]:
    """
    Decorator to log the full result JSON from tool methods.

    This decorator wraps async tool functions and logs their complete result
    in JSON format. Useful for debugging and tracking tool outputs.

    Args:
        logger: Optional logger instance. If not provided, uses __name__ of decorated function.

    Returns:
        Decorator function that logs tool results

    Example:
        @mcp.tool()
        @log_tool_result()
        async def my_tool(param: str) -> dict:
            return {"result": "value"}
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get logger
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            tool_name = func.__name__

            # Call the original function
            result = await func(*args, **kwargs)

            # Log the full result
            try:
                # Try to serialize to JSON for clean output
                result_json = json.dumps(result, default=str, indent=2)
                logger.info(f"TOOL_RESULT [{tool_name}]:\n{result_json}")
            except Exception as e:
                # Fallback to str representation if JSON serialization fails
                logger.info(f"TOOL_RESULT [{tool_name}]:\n{result}")
                logger.warning(f"Failed to serialize result to JSON for {tool_name}: {e}")

            return result

        return wrapper  # type: ignore

    return decorator
