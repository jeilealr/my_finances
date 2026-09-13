from __future__ import annotations

import logging
from pathlib import Path

from my_finances.common.logger import configure_my_finances_logger, get_log_level


def test_get_log_level_falls_back_to_info_for_invalid_value() -> None:
    level, warning = get_log_level("not-a-real-level")

    assert level == logging.INFO
    assert warning is not None
    assert "Invalid log level" in warning


def test_configure_my_finances_logger_replaces_existing_handlers(
    tmp_path: Path,
) -> None:
    logger = configure_my_finances_logger(log_level="INFO")
    assert len(logger.handlers) == 1

    log_file = tmp_path / "my_finances.log"
    logger = configure_my_finances_logger(
        log_level="DEBUG",
        log_file=log_file,
        no_console_logging=False,
    )

    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 2
    assert any(isinstance(handler, logging.FileHandler) for handler in logger.handlers)
    assert log_file.exists()
