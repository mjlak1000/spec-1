"""Tests for core/logging_utils.py."""

from __future__ import annotations

import logging


def test_get_logger_returns_logger():
    from spec1_engine.core.logging_utils import get_logger
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.module"


def test_get_logger_adds_handler():
    from spec1_engine.core.logging_utils import get_logger
    logger = get_logger("test.handler.module")
    assert len(logger.handlers) >= 1


def test_get_logger_with_level():
    from spec1_engine.core.logging_utils import get_logger
    logger = get_logger("test.level.module", level=logging.DEBUG)
    assert logger.level == logging.DEBUG


def test_get_logger_default_level_is_info():
    from spec1_engine.core.logging_utils import get_logger
    # Use a fresh logger name to avoid state from other tests
    logger = get_logger("test.default.level.fresh.xyz123")
    assert logger.level == logging.INFO


def test_configure_root_does_not_raise():
    from spec1_engine.core.logging_utils import configure_root
    configure_root(logging.DEBUG)  # Should not raise
    configure_root(logging.WARNING)  # Should not raise
