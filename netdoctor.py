"""
NetDoctor — AI Troubleshooter (NetForge module)

Connects to one Cisco device or a series over SSH (read-only show commands
only — never modifies config), or reads from saved show output files in
Simulation mode. Sends structured findings to Gemini 2.5 Flash API and
produces a plain-language diagnostic report.

API key: set environment variable GEMINI_API_KEY before running.
  Windows PowerShell : $env:GEMINI_API_KEY="your-key-here"
  Permanent          : setx GEMINI_API_KEY "your-key-here"

built by A. Wassim · github.com/wassimsmt
"""

__author__  = "A. Wassim"
__version__ = "1.0"
__license__ = "MIT"

import os
import re
from datetime import datetime
from getpass import getpass
from pathlib import Path

import ui

GEMINI_MODEL = "gemini-2.5-flash"
OUTPUT_DIR   = Path(__file__).parent / "output"
SIM_DIR      = Path(__file__).parent / "sim_input"

SHOW_COMMANDS = {
    "switch": [
        "show version",
        "show interfaces",
        "show ip interface brief",
        "show vlan brief",
        "show spanning-tree",
        "show mac address-table",
        "show cdp neighbors detail",
        "show etherchannel summary",
        "show port-security",
    ],
    "router": [
        "show version",
        "show interfaces",
        "show ip interface brief",
        "show ip route",
        "show ip ospf neighbor",
        "show ip nat translations",
        "show access-lists",
        "show ip dhcp binding",
        "show ip dhcp conflict",
        "show cdp neighbors detail",
    ],
}
_sw = set(SHOW_COMMANDS["switch"])
SHOW_COMMANDS["both"] = SHOW_COMMANDS["switch"] + [
    c for c in SHOW_COMMANDS["router"] if c not in _sw
]
del _sw

_NUMBERED = re.compile(r"^\d+[).]")


# ===========================================================================
# 1. Entry point
# ===========================================================================
def run():
    ui.section("NetDoctor — AI Troubleshooter")

    mode = connection_menu()
    if mode in (None, "back"):
        return

    devices = build_inventory()
    if not devices:
        ui.warn("No devices defined. Returning to main menu.")
        return

    ui.section("Device Type")
    ui.info("What type of device are you diagnosing?")
    print(f"  {ui.GREEN}[1]{ui.RESET} Switch")
    print(f"  {ui.GREEN}[2]{ui.RESET} Router")
    print(f"  {ui.GREEN}[3]{ui.RESET} Both")
    while True:
        dt = ui.ask(">")
        if dt == "1":
            device_type = "switch"
            break
        if dt == "2":
            device_type = "router"
            break
        if dt == "3":
            device_type = "both"
            break
        ui.warn("Please enter 1, 2, or 3.")

    creds = None
    if mode == "ssh":
        ui.section("SSH Credentials")
        import netforge_config
        saved_user = netforge_config.get("ssh", "username")
        prompt = f"SSH username [{saved_user}]:" if saved_user else "SSH username:"
        typed = ui.ask(prompt)
        username = typed if typed else saved_user
        if username:
            netforge_config.save("ssh", "username", username)
        creds = {
            "username": username,
            "password": getpass("SSH password: "),
            "secret":   getpass("Enable secret (blank if none): "),
        }

    import netforge_log
    for device in devices:
        ui.section(f"Diagnosing {device['name']} ({device['host']})")
        show_data = collect_show_output(device, mode, device_type, creds)
        if show_data is None:
            ui.warn(f"Skipping {device['name']} — collection failed.")
            netforge_log.log("NetDoctor", mode.upper(), device["name"], "SKIPPED")
            continue
        findings = parse_output(show_data, device_type, device["name"])
        report   = ask_gemini(device, findings)
        save_report(device, report)
        display_report(report)
        netforge_log.log("NetDoctor", mode.upper(), device["name"], "SUCCESS")


# ===========================================================================
# 2. Connection menu
# ===========================================================================
def connection_menu():
    ui.info("Choose a connection method:")
    print(f"  {ui.GREEN}[1]{ui.RESET} SSH                               {ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[2]{ui.RESET} Simulation / read from sim_input/  {ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[3]{ui.RESET} Console cable                      {ui.YELLOW}(Coming Soon){ui.RESET}")
    print(f"  {ui.GREEN}[99]{ui.RESET} Back to main menu")
    choice = ui.ask(">")
    if choice == "1":
        return "ssh"
    if choice == "2":
        return "sim"
    if choice == "3":
        ui.coming_soon("Console cable connection")
        return None
    if choice == "99":
        return "back"
    ui.warn("Invalid choice.")
    return None


# ===========================================================================
# 3. Inventory — same pattern as configforge
# ===========================================================================
def build_inventory():
    ui.section("Inventory")
    ui.info("Diagnose a single device or a series?")
    print(f"  {ui.GREEN}[1]{ui.RESET} Single device")
    print(f"  {ui.GREEN}[2]{ui.RESET} Series  (e.g. SW1-FLOOR1 ... SWn-FLOOR1)")
    choice = ui.ask(">")
    if choice == "1":
        return _single_device()
    if choice == "2":
        return _device_series()
    ui.warn("Invalid choice.")
    return []


def _single_device():
    import validators
    name = ui.ask("Device hostname (e.g. SW1-FLOOR1):")
    host = validators.validated_ip(f"Management IP for {name}:", ui.ask)
    return [{"name": name, "host": host}]


def _device_series():
    ui.info("Use {n} in the template where the number goes.")
    template = ui.ask("Name template (e.g. SW{n}-FLOOR1):")
    if "{n}" not in template:
        ui.warn("Template must contain {n}. Aborting series.")
        return []
    start = ui.int_prompt("Start number", default=1)
    count = ui.int_prompt("How many devices", default=3)
    import validators
    devices = []
    for i in range(start, start + count):
        name = template.replace("{n}", str(i))
        host = validators.validated_ip(f"Management IP for {name}:", ui.ask)
        devices.append({"name": name, "host": host})
    return devices


# ===========================================================================
# 4. Show command collection
# ===========================================================================
def collect_show_output(device, mode, device_type, creds=None):
    commands  = SHOW_COMMANDS[device_type]
    show_data = {}

    if mode == "ssh":
        try:
            from netmiko import (ConnectHandler,
                                 NetmikoTimeoutException,
                                 NetmikoAuthenticationException)
        except ImportError:
            ui.error("Netmiko is not installed. Run: pip install -r requirements.txt")
            return None

        conn_params = {
            "device_type": "cisco_ios",
            "host":        device["host"],
            "username":    creds["username"],
            "password":    creds["password"],
            "secret":      creds["secret"],
        }
        ui.info(f"Connecting to {device['name']} ({device['host']}) ...")
        try:
            with ConnectHandler(**conn_params) as conn:
                if creds["secret"]:
                    conn.enable()
                for cmd in commands:
                    ui.info(f"  Running: {cmd}")
                    show_data[cmd] = conn.send_command(cmd)
        except NetmikoAuthenticationException:
            ui.error(f"{device['name']}: authentication failed "
                     f"(check username / password / enable secret).")
            return None
        except NetmikoTimeoutException:
            ui.error(f"{device['name']}: connection timed out "
                     f"(check IP, reachability, and that SSH is enabled).")
            return None
        except Exception as exc:
            ui.error(f"{device['name']}: {exc}")
            return None

    else:  # sim
        device_dir = SIM_DIR / device["name"]
        if not device_dir.exists():
            create_sim_structure(device["name"], device_type)
            ui.warn("Sim input folder created — paste show output into each "
                    "file, then re-run NetDoctor.")
            return None
        for cmd in commands:
            fname    = f"{device['name']}_{cmd.replace(' ', '_')}.txt"
            filepath = device_dir / fname
            if filepath.exists():
                show_data[cmd] = filepath.read_text(encoding="utf-8")
            else:
                ui.warn(f"Missing sim file: {fname}")
                show_data[cmd] = ""

    return show_data


# ===========================================================================
# 5. Deterministic parser
# ===========================================================================
def parse_output(show_data, device_type, device_name="device"):
    issues = []
    clean  = []

    # ── show interfaces ────────────────────────────────────────────────────
    iface_output   = show_data.get("show interfaces", "")
    iface_statuses = {}
    iface_inp_err  = {}
    iface_crc_err  = {}
    current_iface  = None

    for line in iface_output.splitlines():
        # Interface header line: no leading whitespace, contains " is "
        if line and not line[0].isspace() and " is " in line:
            current_iface = line.split(" is ")[0].strip()
            lower = line.lower()
            if "err-disabled" in lower:
                iface_statuses[current_iface] = "err-disabled"
            elif "down, line protocol is down" in lower:
                iface_statuses[current_iface] = "down/down"
            elif "up, line protocol is down" in lower:
                iface_statuses[current_iface] = "up/down"
            elif "up, line protocol is up" in lower:
                iface_statuses[current_iface] = "up/up"
            else:
                iface_statuses[current_iface] = "unknown"
            iface_inp_err[current_iface] = 0
            iface_crc_err[current_iface] = 0

        # Error counters: "N input errors, N CRC, ..." on a single line
        elif current_iface and "input errors" in line and "CRC" in line:
            segs = line.strip().split(",")
            try:
                iface_inp_err[current_iface] = int(segs[0].split()[0])
            except (ValueError, IndexError):
                pass
            for seg in segs:
                if "CRC" in seg:
                    try:
                        iface_crc_err[current_iface] = int(seg.strip().split()[0])
                    except (ValueError, IndexError):
                        pass

    for iface, status in iface_statuses.items():
        ierr = iface_inp_err.get(iface, 0)
        cerr = iface_crc_err.get(iface, 0)
        if status == "err-disabled":
            issues.append({"severity": "high", "area": "Interface", "item": iface,
                           "detail": "err-disabled", "type": "config"})
        elif status == "down/down":
            issues.append({"severity": "high", "area": "Interface", "item": iface,
                           "detail": "status down/down", "type": "physical"})
        elif status == "up/down":
            issues.append({"severity": "high", "area": "Interface", "item": iface,
                           "detail": "up/line-protocol-down", "type": "config"})
        elif status == "up/up":
            flagged = False
            if ierr > 100:
                issues.append({"severity": "medium", "area": "Interface", "item": iface,
                               "detail": f"input errors: {ierr}", "type": "physical"})
                flagged = True
            if cerr > 50:
                issues.append({"severity": "medium", "area": "Interface", "item": iface,
                               "detail": f"CRC errors: {cerr}", "type": "physical"})
                flagged = True
            if not flagged:
                clean.append(f"{iface}: up/up")

    # ── show spanning-tree ─────────────────────────────────────────────────
    stp_output   = show_data.get("show spanning-tree", "")
    stp_blk      = []
    stp_mode_str = ""
    if not stp_output.strip():
        if device_type in ("switch", "both"):
            ui.warn("show spanning-tree: no output — STP may not be configured.")
    else:
        for line in stp_output.splitlines():
            lower = line.lower()
            if "rapid-pvst" in lower:
                stp_mode_str = "rapid-pvst"
            elif "pvst" in lower and not stp_mode_str:
                stp_mode_str = "pvst"
            if " BLK " in line:
                parts = line.strip().split()
                if parts:
                    stp_blk.append(parts[0])

    # ── show ip ospf neighbor ──────────────────────────────────────────────
    ospf_output = show_data.get("show ip ospf neighbor", "")
    if device_type in ("router", "both"):
        if not ospf_output.strip():
            ui.warn("show ip ospf neighbor: no output — OSPF may not be configured.")
        else:
            for line in ospf_output.splitlines():
                parts = line.split()
                if parts and parts[0] and parts[0][0].isdigit():
                    state = parts[2] if len(parts) > 2 else ""
                    if not state.upper().startswith("FULL"):
                        issues.append({"severity": "high", "area": "OSPF",
                                       "item": parts[0],
                                       "detail": f"neighbor state: {state}",
                                       "type": "config"})

    # ── show ip route ──────────────────────────────────────────────────────
    route_output = show_data.get("show ip route", "")
    if device_type in ("router", "both"):
        if not route_output.strip() or route_output.lstrip().startswith("%"):
            issues.append({"severity": "high", "area": "Routing",
                           "item": "routing table",
                           "detail": "routing table is empty",
                           "type": "config"})
        elif "0.0.0.0" not in route_output:
            issues.append({"severity": "medium", "area": "Routing",
                           "item": "default route",
                           "detail": "no default route (0.0.0.0) found",
                           "type": "config"})

    # ── show port-security ─────────────────────────────────────────────────
    ps_output = show_data.get("show port-security", "")
    if ps_output.strip():
        for line in ps_output.splitlines():
            parts = line.strip().split()
            # Summary table data rows: interface name in first column
            if (len(parts) >= 4
                    and parts[0]
                    and parts[0][0].isalpha()
                    and parts[0] not in ("Secure", "Security", "------")):
                try:
                    viol = int(parts[3])
                    if viol > 0:
                        issues.append({"severity": "medium", "area": "Port Security",
                                       "item": parts[0],
                                       "detail": f"security violations: {viol}",
                                       "type": "config"})
                except (ValueError, IndexError):
                    pass
            # Interface-specific detail format: "Security Violation Count   : N"
            if "Security Violation Count" in line:
                try:
                    count = int(line.split(":")[-1].strip())
                    if count > 0:
                        issues.append({"severity": "medium", "area": "Port Security",
                                       "item": "port-security",
                                       "detail": f"Security Violation Count: {count}",
                                       "type": "config"})
                except ValueError:
                    pass

    # ── show etherchannel summary ──────────────────────────────────────────
    ec_output = show_data.get("show etherchannel summary", "")
    if ec_output.strip():
        for line in ec_output.splitlines():
            if "(s)" in line:
                parts = line.strip().split()
                # Port-channel name is in the second column (e.g. "Po2(SU)")
                raw = parts[1] if len(parts) > 1 else (parts[0] if parts else "")
                item = raw.split("(")[0] if raw else "EtherChannel"
                issues.append({"severity": "high", "area": "EtherChannel",
                               "item": item or "EtherChannel",
                               "detail": "member(s) suspended",
                               "type": "config"})

    # ── show ip dhcp conflict ──────────────────────────────────────────────
    dhcp_output = show_data.get("show ip dhcp conflict", "")
    if dhcp_output.strip():
        for line in dhcp_output.splitlines():
            parts = line.strip().split()
            if parts and parts[0] and parts[0][0].isdigit():
                issues.append({"severity": "medium", "area": "DHCP",
                               "item": parts[0],
                               "detail": "DHCP address conflict detected",
                               "type": "config"})

    # ── build raw_summary ──────────────────────────────────────────────────
    n_issues = len(issues)
    n_clean  = len(clean)
    snippets = [
        f"{iss['item']} {iss['detail']} ({iss['type']})"
        for iss in issues[:5]
    ]
    summary_parts = [
        f"Device {device_name} ({device_type}).",
        f"Parser found {n_issues} issue(s)"
        + (": " + "; ".join(snippets) + "." if snippets else "."),
    ]
    if n_clean:
        summary_parts.append(f"{n_clean} interface(s) are clean (up/up).")
    if stp_mode_str:
        stp_note = f"STP is running {stp_mode_str}."
        if stp_blk:
            stp_note += f" Blocked ports: {', '.join(stp_blk)}."
        summary_parts.append(stp_note)
    elif stp_output.strip() and device_type in ("switch", "both"):
        summary_parts.append("STP output present (mode not identified).")
    if not any(i["area"] == "Port Security" for i in issues):
        summary_parts.append("No port security violations.")
    raw_summary = " ".join(summary_parts)

    return {"issues": issues, "clean": clean, "raw_summary": raw_summary}


# ===========================================================================
# 6. Gemini API call
# ===========================================================================
def ask_gemini(device, findings):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        ui.error("GEMINI_API_KEY environment variable not set.")
        ui.info("Set it before running:")
        ui.info("  Windows PowerShell : $env:GEMINI_API_KEY=\"your-key-here\"")
        ui.info("  Permanent          : setx GEMINI_API_KEY \"your-key-here\"")
        return _fallback_report(device, findings)

    prompt = (
        "You are a Cisco network engineer and troubleshooting expert.\n"
        "A network administrator ran diagnostic show commands on a Cisco "
        "device and the following structured findings were produced by "
        "an automated parser. Write a clear, professional diagnostic "
        "report with three sections:\n\n"
        "ISSUES — for each issue: what it is, the most likely cause, "
        "and the exact IOS fix commands if it is a configuration problem, "
        "or state \"physical inspection required\" if it is a hardware/cable "
        "issue.\n\n"
        "CLEAN — brief list of what is working normally.\n\n"
        "RECOMMENDATION — one paragraph summary: how many issues are "
        "config-fixable vs physical, what to do first, and whether to "
        "re-run NetDoctor after applying fixes.\n\n"
        "Do not add any preamble. Start directly with ISSUES.\n"
        "Use plain text only — no markdown, no asterisks, no bullet "
        "symbols. Use numbered lists for issues.\n\n"
        f"Device findings:\n{findings['raw_summary']}"
    )

    try:
        from google import genai
        client   = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as exc:
        ui.error(f"Gemini API error: {exc}")
        return _fallback_report(device, findings)


def _fallback_report(device, findings):
    lines = ["ISSUES", ""]
    if not findings["issues"]:
        lines.append("No issues detected by the parser.")
    else:
        for i, iss in enumerate(findings["issues"], 1):
            lines.append(
                f"{i}) [{iss['severity'].upper()}] {iss['area']} — "
                f"{iss['item']}: {iss['detail']} (type: {iss['type']})"
            )
    lines += ["", "CLEAN", ""]
    if not findings["clean"]:
        lines.append("No clean interfaces recorded.")
    else:
        for i, c in enumerate(findings["clean"], 1):
            lines.append(f"{i}) {c}")
    lines += [
        "", "RECOMMENDATION", "",
        "AI analysis unavailable (GEMINI_API_KEY not set or API error). "
        "Review the ISSUES section above. Config-type issues can be fixed "
        "via IOS CLI. Physical-type issues require on-site inspection.",
    ]
    return "\n".join(lines)


# ===========================================================================
# 7. Save and display report
# ===========================================================================
def save_report(device, report_text):
    OUTPUT_DIR.mkdir(exist_ok=True)
    filename  = OUTPUT_DIR / f"{device['name']}_report.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = "\n".join([
        f"! NetDoctor Report — {device['name']} ({device['host']})",
        "! Generated by NetForge NetDoctor v1.0 — built by A. Wassim",
        "! github.com/wassimsmt",
        f"! Date: {timestamp}",
        "! " + "─" * 41,
    ])
    filename.write_text(header + "\n" + report_text + "\n", encoding="utf-8")
    ui.ok(f"Report saved: {filename}")


def display_report(report_text):
    ui.section("NetDoctor Report")
    for line in report_text.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(kw) for kw in ("ISSUES", "CLEAN", "RECOMMENDATION")):
            print(f"{ui.CYAN}{ui.BRIGHT}{line}{ui.RESET}")
        elif stripped and _NUMBERED.match(stripped):
            print(f"{ui.YELLOW}{line}{ui.RESET}")
        else:
            print(f"{ui.WHITE}{line}{ui.RESET}")


# ===========================================================================
# Simulation mode setup helper
# ===========================================================================
def create_sim_structure(device_name, device_type):
    device_dir = SIM_DIR / device_name
    device_dir.mkdir(parents=True, exist_ok=True)
    commands = SHOW_COMMANDS[device_type]
    for cmd in commands:
        fname = f"{device_name}_{cmd.replace(' ', '_')}.txt"
        fpath = device_dir / fname
        if not fpath.exists():
            fpath.write_text("", encoding="utf-8")
    ui.info(f"Created sim_input/{device_name}/ with {len(commands)} files.")
    ui.info("Paste the output of each show command into the corresponding .txt file.")
    ui.info(f"File naming example: {device_name}_show_interfaces.txt")
