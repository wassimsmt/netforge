"""
NetForge input validators.
built by A. Wassim · github.com/wassimsmt
"""

__author__  = "A. Wassim"
__version__ = "1.0"
__license__ = "MIT"

import ipaddress
import re


def is_valid_ip(ip_str):
    """Returns True if ip_str is a valid IPv4 address."""
    try:
        ipaddress.IPv4Address(ip_str.strip())
        return True
    except ValueError:
        return False


def is_valid_subnet(subnet_str):
    """Returns True if subnet_str is a valid IPv4 network (e.g. 192.168.1.0/24)."""
    try:
        ipaddress.IPv4Network(subnet_str.strip(), strict=False)
        return True
    except ValueError:
        return False


def is_valid_hostname(hostname_str):
    """Returns True if hostname_str is a valid Cisco hostname (1-63 chars,
    letters/digits/hyphens, must start with letter)."""
    if not hostname_str:
        return False
    pattern = r'^[A-Za-z][A-Za-z0-9\-]{0,62}$'
    return bool(re.match(pattern, hostname_str))


def validated_ip(prompt_fn, ask_fn):
    """Ask for an IP address, re-prompt until valid.
    prompt_fn: string prompt text
    ask_fn: the ui.ask function"""
    while True:
        val = ask_fn(prompt_fn)
        if is_valid_ip(val):
            return val
        import ui
        ui.warn(f"'{val}' is not a valid IPv4 address. Example: 192.168.1.1")


def validated_subnet(prompt_fn, ask_fn):
    """Ask for a subnet, re-prompt until valid."""
    while True:
        val = ask_fn(prompt_fn)
        if is_valid_subnet(val):
            return val
        import ui
        ui.warn(f"'{val}' is not a valid subnet. Example: 192.168.1.0/24")
