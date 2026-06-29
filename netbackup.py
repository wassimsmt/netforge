"""
NetBackup — Config Backup Manager (NetForge module)

Connects to Cisco devices over SSH and saves each
device's running configuration to a timestamped backup
file. Strictly read-only — never modifies device config.

Backups saved to: backups/<hostname>/<hostname>_<timestamp>.txt

built by A. Wassim · github.com/wassimsmt
"""
from datetime import datetime
from getpass import getpass
from pathlib import Path

import ui
from rich.table import Table

BACKUP_DIR = Path(__file__).parent / "backups"


# ===========================================================================
# Entry point
# ===========================================================================
def run():
    ui.section("NetBackup — Config Backup Manager")

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
        ui.section(f"Backing up {device['name']} ({device['host']})")
        config = collect_config(device, mode, creds)
        if config is None:
            ui.warn(f"Skipping {device['name']} — collection failed.")
            results.append((device["name"], False, None))
            continue
        filepath = save_backup(device, config)
        results.append((device["name"], True, filepath))

    display_summary(results)


# ===========================================================================
# 1. Connection menu
# ===========================================================================
def connection_menu():
    ui.info("Choose a connection method:")
    print(f"  {ui.GREEN}[1]{ui.RESET} SSH                              {ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[2]{ui.RESET} Simulation / generate template   {ui.GREEN}ready{ui.RESET}")
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
# 2. Inventory
# ===========================================================================
def build_inventory():
    ui.section("Inventory")
    ui.info("Back up a single device or a series?")
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
# 3. Collect running-config
# ===========================================================================
def collect_config(device, mode, creds=None):
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
        timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M")
        device_dir = BACKUP_DIR / device["name"]
        device_dir.mkdir(parents=True, exist_ok=True)
        filepath   = device_dir / f"{device['name']}_SIMULATED_{timestamp}.txt"
        template   = "\n".join([
            f"! SIMULATED BACKUP — {device['name']} ({device['host']})",
            "! Replace this file content with real",
            "! show running-config output for testing.",
            "! Generated by NetForge NetBackup v1.0",
            "!",
            "! Paste your running-config below this line:",
        ])
        filepath.write_text(template, encoding="utf-8")
        ui.info(f"Template created: {filepath}")
        ui.info("Paste real config into this file to test backup restore workflows.")
        return template


# ===========================================================================
# 4. Save backup
# ===========================================================================
def save_backup(device, config):
    timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M")
    device_dir = BACKUP_DIR / device["name"]
    device_dir.mkdir(parents=True, exist_ok=True)
    filename   = device_dir / f"{device['name']}_{timestamp}.txt"
    ts_full    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header     = "\n".join([
        f"! NetBackup — {device['name']} ({device['host']})",
        "! Backed up by NetForge NetBackup v1.0",
        "! built by A. Wassim · github.com/wassimsmt",
        f"! Timestamp: {ts_full}",
        "! " + "─" * 41,
    ]) + "\n"
    filename.write_text(header + config, encoding="utf-8")
    ui.ok(f"Backup saved: {filename}")
    return filename


# ===========================================================================
# 5. Summary
# ===========================================================================
def display_summary(results):
    table = Table(title="Backup Summary", header_style="bold cyan",
                  border_style="blue", show_lines=False)
    table.add_column("Device", style="white", min_width=25)
    table.add_column("Status", style="white", width=12)
    table.add_column("File",   style="white", min_width=30)

    n_ok = 0
    for name, success, filepath in results:
        if success:
            status = "[green]✔ Saved[/green]"
            fname  = filepath.name
            n_ok  += 1
        else:
            status = "[red]✘ Failed[/red]"
            fname  = "—"
        table.add_row(name, status, fname)

    ui.console.print()
    ui.console.print(table)

    if n_ok:
        ui.ok(f"{n_ok} backup(s) saved to backups/")
    else:
        ui.warn("No backups were saved.")
