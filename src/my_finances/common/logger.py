"""Logging utilities used by the command line tools."""

from __future__ import annotations

import inspect
import logging
from contextlib import AbstractContextManager
from functools import wraps
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
LOG_LEVEL_STR = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def _coerce_level(
    level: int | str | None,
    *,
    count_verbose: int = 0,
    count_quiet: int = 0,
) -> tuple[int, str | None]:
    """Resolve a numeric log level and an optional warning message."""
    if level is None:
        resolved_level = logging.INFO - (10 * count_verbose) + (10 * count_quiet)
        return max(logging.DEBUG, min(logging.CRITICAL, resolved_level)), None

    if isinstance(level, int):
        return level, None

    if not isinstance(level, str):
        return logging.INFO, f"Invalid log level type: {type(level)!r}. Using INFO."

    normalized = level.upper()
    if normalized not in LOG_LEVELS:
        return logging.INFO, f"Invalid log level: {level!r}. Using INFO."
    return LOG_LEVELS[normalized], None


def get_log_level(
    level: int | str | None = None,
    count_verbose: int = 0,
    count_quiet: int = 0,
) -> tuple[int, str | None]:
    """Return the resolved log level and any validation warning."""
    return _coerce_level(
        level,
        count_verbose=count_verbose,
        count_quiet=count_quiet,
    )


def get_lowest_level(
    log_level: int | str | None,
    log_file_level: int | str | None,
    count_verbose: int,
    count_quiet: int,
) -> tuple[int, str | None, str | None]:
    """Return the most verbose level required by the active handlers."""
    console_level, console_warning = get_log_level(
        log_level,
        count_verbose=count_verbose,
        count_quiet=count_quiet,
    )
    if log_file_level is None:
        return console_level, console_warning, None

    file_level, file_warning = get_log_level(log_file_level)
    return min(console_level, file_level), console_warning, file_warning


def _reset_handlers(logger: logging.Logger) -> None:
    """Remove and close all handlers attached to a logger.

    This keeps repeated CLI invocations from duplicating log lines.
    """

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def configure_my_finances_logger(
    log_level: int | str | None = None,
    count_verbose: int = 0,
    count_quiet: int = 0,
    log_file: str | Path | None = None,
    log_file_level: int | str | None = None,
    no_console_logging: bool = False,
) -> logging.Logger:
    """Configure the package logger used by the CLI."""

    logger = logging.getLogger("my_finances")
    logger.propagate = False
    _reset_handlers(logger)

    formatter = logging.Formatter(LOG_FORMAT)
    general_level, console_warning, file_warning = get_lowest_level(
        log_level=log_level,
        log_file_level=log_file_level,
        count_verbose=count_verbose,
        count_quiet=count_quiet,
    )
    logger.setLevel(general_level)

    if not no_console_logging:
        console_level, _ = get_log_level(
            log_level,
            count_verbose=count_verbose,
            count_quiet=count_quiet,
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(console_level)
        logger.addHandler(console_handler)

    if log_file is not None:
        log_file_path = Path(log_file).expanduser()
        if log_file_path.suffix:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_level, _ = get_log_level(log_file_level or general_level)
            file_handler = logging.FileHandler(log_file_path, mode="w")
            file_handler.setFormatter(formatter)
            file_handler.setLevel(file_level)
            logger.addHandler(file_handler)
        else:
            logger.warning("Ignoring log file without a filename suffix: %s", log_file)

    if console_warning is not None:
        logger.warning(console_warning)
    if file_warning is not None:
        logger.warning(file_warning)

    return logger


def _format_bound_arguments(
    func: Callable[..., object], *args: object, **kwargs: object
) -> str:
    """Return a readable multi-line view of the non-None arguments."""
    signature = inspect.signature(func)
    bound_arguments = signature.bind(*args, **kwargs)
    bound_arguments.apply_defaults()
    non_none_args = {
        key: value
        for key, value in bound_arguments.arguments.items()
        if value is not None
    }
    if not non_none_args:
        return f"Function '{func.__name__}' called without non-None arguments."

    lines = [f"Function '{func.__name__}' called with:"]
    lines.extend(f"  {key}: {value}" for key, value in non_none_args.items())
    return "\n".join(lines)


def log_arguments(
    log_level: str = "DEBUG",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Log all non-None arguments passed to a function."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            logger = logging.getLogger(inspect.getmodule(func).__name__)
            message = _format_bound_arguments(func, *args, **kwargs)
            if log_level.upper() == "INFO":
                logger.info(message)
            else:
                logger.debug(message)

            try:
                return func(*args, **kwargs)
            except Exception:
                with ErrorLogger(logger):
                    raise

        return wrapper

    return decorator


def log_errors(
    raise_exceptions: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R | None]]:
    """Log function context whenever an exception escapes."""

    def decorator(func: Callable[P, R]) -> Callable[P, R | None]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
            logger = logging.getLogger(inspect.getmodule(func).__name__)
            message = _format_bound_arguments(func, *args, **kwargs)
            try:
                return func(*args, **kwargs)
            except Exception as error:
                logger.error("Error while running %s", func.__name__)
                logger.error(message)
                if raise_exceptions:
                    with ErrorLogger(logger):
                        raise
                logger.exception(error)
                return None

        return wrapper

    return decorator


class ErrorLogger(AbstractContextManager["ErrorLogger"]):
    """Context manager that logs exceptions on exit."""

    def __init__(
        self,
        logger: str | logging.Logger | None = None,
        do_log: bool = True,
    ) -> None:
        self.logger_name = logger.name if isinstance(logger, logging.Logger) else logger
        self.do_log = do_log

    def __enter__(self) -> ErrorLogger:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_value is not None and self.do_log:
            logging.getLogger(self.logger_name).exception(exc_value)
