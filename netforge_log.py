"""
NetForge audit logger.
Writes timestamped entries to logs/netforge.log.
Passwords are never logged.
built by A. Wassim · github.com/wassimsmt
"""

__author__  = "A. Wassim"
__version__ = "1.0"
__license__ = "MIT"

import logging
from pathlib import Path

LOG_DIR  = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "netforge.log"


def _get_logger():
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("netforge")
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log(module, mode, target, status, detail=""):
    """
    Log one NetForge action.
    module: "ConfigForge" / "NetDoctor" / etc.
    mode:   "SSH" / "Simulation"
    target: device hostname or subnet
    status: "SUCCESS" / "FAILED" / "SKIPPED"
    detail: optional extra info (no passwords)
    """
    msg = f"{module} | {mode} | {target} | {status}"
    if detail:
        msg += f" | {detail}"
    _get_logger().info(msg)
