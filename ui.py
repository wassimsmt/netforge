"""
NetForge — shared UI helpers (colors, banner, input prompts).

Colors degrade gracefully: if 'colorama' is not installed the toolkit still
runs, just without color. Install colors with:  pip install -r requirements.txt

built by A. Wassim  ·  github.com/wassimsmt
"""

# ---------------------------------------------------------------------------
# Colors (graceful fallback if colorama is missing)
# ---------------------------------------------------------------------------
try:
    from colorama import Fore, Style, init
    init(autoreset=False)  # we manage resets manually inside f-strings
    CYAN, GREEN, YELLOW = Fore.CYAN, Fore.GREEN, Fore.YELLOW
    RED, BLUE, MAGENTA, WHITE = Fore.RED, Fore.BLUE, Fore.MAGENTA, Fore.WHITE
    DIM, BRIGHT, RESET = Style.DIM, Style.BRIGHT, Style.RESET_ALL
except ImportError:  # colorama not installed -> no colors, still works
    CYAN = GREEN = YELLOW = RED = BLUE = MAGENTA = WHITE = ""
    DIM = BRIGHT = RESET = ""

# ---------------------------------------------------------------------------
# Identity / branding
# ---------------------------------------------------------------------------
APP_NAME = "NetForge"
TAGLINE = "Network Automation Toolkit"
VERSION = "v1.0"
AUTHOR = "A. Wassim"
GITHUB = "https://github.com/wassimsmt"
LINKEDIN = "https://www.linkedin.com/in/wassim-abelghouch/"


def banner():
    """Print the colored NetForge banner."""
    art = r"""
 ███╗   ██╗███████╗████████╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗
 ████╗  ██║██╔════╝╚══██╔══╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
 ██╔██╗ ██║█████╗     ██║   █████╗  ██║   ██║██████╔╝██║  ███╗█████╗
 ██║╚██╗██║██╔══╝     ██║   ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
 ██║ ╚████║███████╗   ██║   ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
 ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
"""
    print(CYAN + BRIGHT + art + RESET)
    print(f"{WHITE}{BRIGHT}        {TAGLINE}  ·  {VERSION}{RESET}")
    print(f"{DIM}        built by {AUTHOR}{RESET}")
    print(f"{DIM}        GitHub   : {GITHUB}{RESET}")
    print(f"{DIM}        LinkedIn : {LINKEDIN}{RESET}")
    print()


# ---------------------------------------------------------------------------
# Consistent status lines
# ---------------------------------------------------------------------------
def ok(msg):    print(f"{GREEN}[OK]{RESET} {msg}")
def info(msg):  print(f"{CYAN}[*]{RESET} {msg}")
def warn(msg):  print(f"{YELLOW}[!]{RESET} {msg}")
def error(msg): print(f"{RED}[X]{RESET} {msg}")


def section(title):
    print()
    print(f"{BLUE}{BRIGHT}== {title} =={RESET}")


def coming_soon(name):
    print(f"{YELLOW}{name} is coming soon — stay tuned.{RESET}")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------
def ask(prompt):
    return input(f"{CYAN}{prompt}{RESET} ").strip()


def yes_no(question, default=True):
    suffix = "Y/n" if default else "y/N"
    ans = input(f"{CYAN}{question} ({suffix}){RESET} ").strip().lower()
    if ans == "":
        return default
    return ans in ("y", "yes")


def int_prompt(question, default=None):
    while True:
        raw = input(f"{CYAN}{question}"
                    f"{f' [{default}]' if default is not None else ''}:{RESET} ").strip()
        if raw == "" and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            warn("Please enter a whole number.")
