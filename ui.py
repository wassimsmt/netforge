"""
NetForge — shared UI helpers (colors, banner, input prompts).

built by A. Wassim  ·  github.com/wassimsmt
"""

import sys
import pyfiglet
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.theme import Theme

# ---------------------------------------------------------------------------
# ANSI color constants — used by configforge/netdoctor in plain print() calls.
# Rich initializes Windows ANSI support on import, so these work without colorama.
# ---------------------------------------------------------------------------
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
CYAN    = "\033[36m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
WHITE   = "\033[37m"
DIM     = "\033[2m"
BRIGHT  = "\033[1m"
RESET   = "\033[0m"

# ---------------------------------------------------------------------------
# Rich console with custom theme
# ---------------------------------------------------------------------------
_theme = Theme({
    "ok":      "bold green",
    "info":    "bold cyan",
    "warn":    "bold yellow",
    "error":   "bold red",
    "section": "bold blue",
    "dim":     "dim white",
})
console = Console(theme=_theme, highlight=False)

# ---------------------------------------------------------------------------
# Identity / branding
# ---------------------------------------------------------------------------
APP_NAME = "NetForge"
TAGLINE  = "Network Automation Toolkit"
VERSION  = "v1.0"
AUTHOR   = "A. Wassim"
GITHUB   = "github.com/wassimsmt"
LINKEDIN = "linkedin.com/in/wassim-abelghouch"


def banner():
    """Print the NetForge banner using pyfiglet + Rich."""
    title = pyfiglet.figlet_format("NetForge", font="slant", width=80)
    console.print(f"[cyan]{title}[/cyan]")
    console.print(Panel(
        f"[bold white]{TAGLINE}  ·  {VERSION}[/bold white]\n"
        f"[dim]built by {AUTHOR}[/dim]\n"
        f"[dim]{GITHUB}[/dim]\n"
        f"[dim]{LINKEDIN}[/dim]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print("  [dim]MIT License · v1.0[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Consistent status lines
# ---------------------------------------------------------------------------
def ok(msg):    console.print(f"[ok][[OK]][/ok] {msg}")
def info(msg):  console.print(f"[info][*][/info] {msg}")
def warn(msg):  console.print(f"[warn][!][/warn] {msg}")
def error(msg): console.print(f"[error][X][/error] {msg}")


def section(title):
    console.print()
    console.print(Rule(title, style="bold blue"))


def coming_soon(name):
    console.print(f"[warn]{name} is coming soon — stay tuned.[/warn]")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------
def ask(prompt):
    return input(f"\033[36m{prompt}\033[0m ").strip()


def yes_no(question, default=True):
    suffix = "Y/n" if default else "y/N"
    ans = input(f"\033[36m{question} ({suffix})\033[0m ").strip().lower()
    if ans == "":
        return default
    return ans in ("y", "yes")


def int_prompt(question, default=None):
    while True:
        raw = input(f"\033[36m{question}"
                    f"{f' [{default}]' if default is not None else ''}:\033[0m ").strip()
        if raw == "" and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            warn("Please enter a whole number.")
