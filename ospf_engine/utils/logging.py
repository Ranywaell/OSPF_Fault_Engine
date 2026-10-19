"""Single configured logger so the engine prints predictably from CLI/UI."""

from __future__ import annotations

import logging
import os

_LOGGER_NAME = "ospf_engine"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    level = os.environ.get("OSPF_ENGINE_LOG", "WARNING").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
