"""Structured logging for EarningsLens.

Logs go to both console (INFO+) and data/earningslens.log (DEBUG+).
"""

import logging
import sys
from pathlib import Path


def setup_logger(log_path: Path, name: str = "earningslens") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)-8s | %(message)s")
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
