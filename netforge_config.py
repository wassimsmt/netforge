"""
NetForge configuration file manager.
Reads and writes netforge.ini for user preferences.
built by A. Wassim · github.com/wassimsmt
"""

__author__  = "A. Wassim"
__version__ = "1.0"
__license__ = "MIT"

import configparser
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "netforge.ini"

DEFAULTS = {
    "ssh": {
        "username":    "",
        "timeout":     "30",
        "port":        "22",
    },
    "preferences": {
        "default_device_type": "",
        "save_config":         "true",
    },
}


def load():
    """Load config from netforge.ini. Creates it with defaults if missing."""
    cfg = configparser.ConfigParser()
    if not CONFIG_FILE.exists():
        for section, values in DEFAULTS.items():
            cfg[section] = values
        with open(CONFIG_FILE, "w") as f:
            cfg.write(f)
    cfg.read(CONFIG_FILE)
    return cfg


def get(section, key, fallback=""):
    """Get a single value from the config."""
    cfg = load()
    return cfg.get(section, key, fallback=fallback)


def save(section, key, value):
    """Write a single value back to netforge.ini."""
    cfg = load()
    if section not in cfg:
        cfg[section] = {}
    cfg[section][key] = value
    with open(CONFIG_FILE, "w") as f:
        cfg.write(f)
