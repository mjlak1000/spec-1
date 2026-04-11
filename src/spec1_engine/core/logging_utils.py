"""Logging utilities for SPEC-1."""

from __future__ import annotations

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a configured logger for the given name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )
        logger.addHandler(handler)
    if level is not None:
        logger.setLevel(level)
    elif logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    return logger


def configure_root(level: int = logging.INFO) -> None:
    """Configure the root logger."""
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
