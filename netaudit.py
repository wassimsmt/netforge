"""
NetAudit — Compliance Checker (NetForge module)

Connects to Cisco devices over SSH (read-only) or reads
from saved running-config files in Simulation mode.
Checks device configuration against a user-defined
compliance baseline (baseline.json) and produces a
pass/fail compliance report.

Edit baseline.json to customize compliance rules for
your organization. A default CCNA security baseline
is created automatically on first run.

built by A. Wassim · github.com/wassimsmt
"""
import json
import os
import re
from datetime import datetime
from getpass import getpass
from pathlib import Path

import ui
from rich.table import Table

OUTPUT_DIR    = Path(__file__).parent / "output"
BASELINE_FILE = Path(__file__).parent / "baseline.json"
SIM_DIR       = Path(__file__).parent / "sim_input"

_DEFAULT_BASELINE = [
    {
        "id": "SEC-001",
        "description": "Enable secret must be configured",
        "check_type": "must_contain",
        "value": "enable secret",
        "severity": "critical",
        "fix": "enable secret <your-password>"
    },
    {
        "id": "SEC-002",
        "description": "Service password-encryption must be enabled",
        "check_type": "must_match_regex",
        "value": "^service password-encryption$",
        "severity": "high",
        "fix": "service password-encryption"
    },
    {
        "id": "SEC-003",
        "description": "SSH version 2 must be configured",
        "check_type": "must_contain",
        "value": "ip ssh version 2",
        "severity": "critical",
        "fix": "ip ssh version 2"
    },
    {
        "id": "SEC-004",
        "description": "HTTP server must be disabled",
        "check_type": "must_not_contain",
        "value": "ip http server",
        "severity": "high",
        "fix": "no ip http server"
    },
    {
        "id": "SEC-005",
        "description": "Banner motd must be configured",
        "check_type": "must_contain",
        "value": "banner motd",
        "severity": "medium",
        "fix": "banner motd #Unauthorized access prohibited#"
    },
    {
        "id": "SEC-006",
        "description": "Console exec-timeout must be configured",
        "check_type": "must_contain",
        "value": "exec-timeout",
        "severity": "medium",
        "fix": "line console 0\n exec-timeout 10 0"
    },
    {
        "id": "SEC-007",
        "description": "VTY lines must use SSH only (no telnet)",
        "check_type": "must_contain",
        "value": "transport input ssh",
        "severity": "critical",
        "fix": "line vty 0 15\n transport input ssh"
    },
    {
        "id": "SEC-008",
        "description": "VTY lines must use local login",
        "check_type": "must_contain",
        "value": "login local",
        "severity": "high",
        "fix": "line vty 0 15\n login local"
    },
    {
        "id": "SEC-009",
        "description": "no ip domain-lookup should be configured",
        "check_type": "must_contain",
        "value": "no ip domain-lookup",
        "severity": "low",
        "fix": "no ip domain-lookup"
    },
    {
        "id": "SEC-010",
        "description": "Telnet must not be permitted on VTY lines",
        "check_type": "must_not_contain",
        "value": "transport input telnet",
        "severity": "critical",
        "fix": "line vty 0 15\n transport input ssh"
    }
]


# ===========================================================================
# Entry point
# ===========================================================================
def run():
    ui.section("NetAudit — Compliance Checker")

    baseline = load_baseline()
    ui.info(f"Loaded baseline: {len(baseline)} rules from {BASELINE_FILE.name}")

    mode = connection_menu()
    if mode is None or mode == "back":
        return

    devices = build_inventory()
    if not devices:
        ui.warn("No devices defined.")
        return

    creds = None
    if mode == "ssh":
        ui.section("SSH Credentials")
        creds = {
            "username": ui.ask("SSH username:"),
            "password": getpass("SSH password: "),
            "secret":   getpass("Enable secret (blank if none): "),
        }

    results = []
    for device in devices:
        ui.section(f"Auditing {device['name']} ({device['host']})")
        running_config = collect_running_config(device, mode, creds)
        if running_config is None:
            ui.warn(f"Skipping {device['name']} — could not collect config.")
            continue
        audit_result = run_audit(device, running_config, baseline)
        save_report(device, audit_result)
        display_report(device, audit_result)
        results.append((device["name"], audit_result))

    if len(results) > 1:
        display_summary(results)


# ===========================================================================
# 1. Baseline
# ===========================================================================
def load_baseline():
    if not BASELINE_FILE.exists():
        BASELINE_FILE.write_text(
            json.dumps(_DEFAULT_BASELINE, indent=2), encoding="utf-8"
        )
        ui.info(f"Created default baseline: {BASELINE_FILE}")
        ui.info("Edit baseline.json to customize compliance rules.")
    try:
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        ui.error(f"baseline.json is not valid JSON: {exc}")
        return []


# ===========================================================================
# 2. Connection menu
# ===========================================================================
def connection_menu():
    ui.info("Choose a connection method:")
    print(f"  {ui.GREEN}[1]{ui.RESET} SSH                              {ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[2]{ui.RESET} Simulation / read from file      {ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[3]{ui.RESET} Console cable                    {ui.YELLOW}(Coming Soon){ui.RESET}")
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
# 3. Inventory
# ===========================================================================
def build_inventory():
    ui.section("Inventory")
    ui.info("Audit a single device or a series?")
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
    name = ui.ask("Device hostname (e.g. SW1-FLOOR1):")
    host = ui.ask(f"Management IP for {name}:")
    return [{"name": name, "host": host}]


def _device_series():
    ui.info("Use {n} in the template where the number goes.")
    template = ui.ask("Name template (e.g. SW{n}-FLOOR1):")
    if "{n}" not in template:
        ui.warn("Template must contain {n}. Aborting series.")
        return []
    start = ui.int_prompt("Start number", default=1)
    count = ui.int_prompt("How many devices", default=3)
    devices = []
    for i in range(start, start + count):
        name = template.replace("{n}", str(i))
        host = ui.ask(f"Management IP for {name}:")
        devices.append({"name": name, "host": host})
    return devices


# ===========================================================================
# 4. Collect running-config
# ===========================================================================
def collect_running_config(device, mode, creds=None):
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
                ui.info("Running: show running-config")
                return conn.send_command("show running-config")
        except NetmikoAuthenticationException:
            ui.error(f"{device['name']}: authentication failed.")
            return None
        except NetmikoTimeoutException:
            ui.error(f"{device['name']}: connection timed out.")
            return None
        except Exception as exc:
            ui.error(f"{device['name']}: {exc}")
            return None

    else:  # sim
        device_dir = SIM_DIR / device["name"]
        filepath   = device_dir / f"{device['name']}_running_config.txt"

        if not device_dir.exists():
            device_dir.mkdir(parents=True, exist_ok=True)
            filepath.write_text("", encoding="utf-8")
            ui.info(f"Created sim_input/{device['name']}/")
            ui.info(f"Paste the running-config output into: {filepath.name}")
            ui.info("Then re-run NetAudit to generate the compliance report.")
            return None

        if not filepath.exists() or not filepath.read_text(encoding="utf-8").strip():
            ui.warn(f"Sim file is empty: {filepath.name}")
            ui.warn("Paste the running-config into the file, then re-run.")
            return None

        return filepath.read_text(encoding="utf-8")


# ===========================================================================
# 5. Audit engine
# ===========================================================================
def run_audit(device, running_config, baseline):
    passed, failed = [], []
    for rule in baseline:
        check = rule["check_type"]
        value = rule["value"]
        if check == "must_contain":
            ok = value in running_config
        elif check == "must_not_contain":
            ok = value not in running_config
        elif check == "must_match_regex":
            ok = bool(re.search(value, running_config, re.MULTILINE))
        else:
            ok = False
        (passed if ok else failed).append(rule)
    score = int(len(passed) / len(baseline) * 100) if baseline else 0
    return {"device": device, "passed": passed, "failed": failed, "score": score}


# ===========================================================================
# 6. Save report
# ===========================================================================
def save_report(device, audit_result):
    OUTPUT_DIR.mkdir(exist_ok=True)
    filename  = OUTPUT_DIR / f"{device['name']}_audit.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n_passed  = len(audit_result["passed"])
    n_failed  = len(audit_result["failed"])
    n_total   = n_passed + n_failed
    score     = audit_result["score"]

    lines = [
        f"! NetAudit Report — {device['name']} ({device['host']})",
        "! Generated by NetForge NetAudit v1.0 — built by A. Wassim",
        "! github.com/wassimsmt",
        f"! Date: {timestamp}",
        f"! Baseline: {BASELINE_FILE.name} ({n_total} rules)",
        f"! Score: {score}% ({n_passed}/{n_total} rules passed)",
        "! " + "─" * 41,
        "",
        f"FAILED RULES ({n_failed})",
    ]
    for rule in audit_result["failed"]:
        lines += [
            "",
            f"[{rule['severity'].upper()}] {rule['id']} — {rule['description']}",
            f"Fix: {rule['fix']}",
        ]
    lines += [
        "",
        f"PASSED RULES ({n_passed})",
    ]
    for rule in audit_result["passed"]:
        lines.append(f"[PASS] {rule['id']} — {rule['description']}")

    filename.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ui.ok(f"Report saved: {filename}")


# ===========================================================================
# 7. Display report
# ===========================================================================
def display_report(device, audit_result):
    ui.section(f"Audit Report — {device['name']}")
    score = audit_result["score"]

    if score == 100:
        print(f"{ui.GREEN}COMPLIANT  {score}%{ui.RESET}")
    elif score >= 70:
        print(f"{ui.YELLOW}PARTIAL  {score}%{ui.RESET}")
    else:
        print(f"{ui.RED}NON-COMPLIANT  {score}%{ui.RESET}")
    print()

    if audit_result["failed"]:
        print(f"{ui.BRIGHT}FAILED RULES:{ui.RESET}")
        for rule in audit_result["failed"]:
            color = ui.RED if rule["severity"] in ("critical", "high") else ui.YELLOW
            print(f"{color}  [{rule['severity'].upper()}] {rule['id']} — "
                  f"{rule['description']}{ui.RESET}")
            print(f"{color}  Fix: {rule['fix']}{ui.RESET}")
            print()

    if audit_result["passed"]:
        print(f"{ui.BRIGHT}PASSED RULES:{ui.RESET}")
        for rule in audit_result["passed"]:
            print(f"{ui.GREEN}  [PASS] {rule['id']} — {rule['description']}{ui.RESET}")


# ===========================================================================
# 8. Multi-device summary
# ===========================================================================
def display_summary(results):
    table = Table(title="Audit Summary", header_style="bold cyan",
                  border_style="blue", show_lines=False)
    table.add_column("Device", style="white", min_width=25)
    table.add_column("Score",  style="white", width=8)
    table.add_column("Status", style="white", width=16)

    for name, audit_result in results:
        score = audit_result["score"]
        if score == 100:
            status = "[green]COMPLIANT[/green]"
        elif score >= 70:
            status = "[yellow]PARTIAL[/yellow]"
        else:
            status = "[red]NON-COMPLIANT[/red]"
        table.add_row(name, f"{score}%", status)

    ui.console.print()
    ui.console.print(table)
