"""
NetScan — Network Discovery Tool (NetForge module)

Discovers live hosts on a subnet using parallel ping,
checks SSH port availability, and optionally identifies
Cisco devices by connecting via Netmiko.

Strictly read-only — never modifies device config.

Output: output/netscan_<subnet>_<timestamp>.txt

built by A. Wassim · github.com/wassimsmt
"""

__author__  = "A. Wassim"
__version__ = "1.0"
__license__ = "MIT"

import ipaddress
import socket
import subprocess
import concurrent.futures
from datetime import datetime
from getpass import getpass
from pathlib import Path

import ui
from rich.table import Table
from rich.progress import (Progress, SpinnerColumn,
                           TextColumn, BarColumn, TaskProgressColumn)

OUTPUT_DIR   = Path(__file__).parent / "output"
MAX_WORKERS  = 50
SSH_PORT     = 22
SSH_TIMEOUT  = 3
PING_TIMEOUT = 500


# ===========================================================================
# Entry point
# ===========================================================================
def run():
    ui.section("NetScan — Network Discovery")

    import validators
    subnet_str = validators.validated_subnet(
        "Subnet to scan (e.g. 192.168.1.0/24):", ui.ask)
    network = ipaddress.IPv4Network(subnet_str, strict=False)

    host_count = network.num_addresses - 2
    if host_count <= 0:
        ui.error("Subnet too small to scan.")
        return
    ui.info(f"Scanning {host_count} hosts on {network} ...")
    if host_count > 254:
        if not ui.yes_no(
                f"This will ping {host_count} hosts. Continue?",
                default=False):
            return

    identify = ui.yes_no(
        "Attempt SSH identification on live hosts?",
        default=False)

    creds = None
    if identify:
        ui.section("SSH Credentials for identification")
        creds = {
            "username": ui.ask("SSH username:"),
            "password": getpass("SSH password: "),
            "secret":   getpass("Enable secret (blank if none): "),
        }

    hosts = [str(h) for h in network.hosts()]

    ui.info("Phase 1 — Ping sweep ...")
    live_hosts = ping_sweep(hosts)
    ui.ok(f"{len(live_hosts)} host(s) responding to ping.")

    if not live_hosts:
        ui.warn("No live hosts found.")
        return

    ui.info("Phase 2 — SSH port check ...")
    ssh_results = check_ssh_ports(live_hosts)

    scan_results = []
    if identify and creds:
        ui.info("Phase 3 — Cisco device identification ...")
        scan_results = identify_devices(live_hosts, ssh_results, creds)
    else:
        for host in live_hosts:
            scan_results.append({
                "host":       host,
                "alive":      True,
                "ssh_open":   ssh_results.get(host, False),
                "hostname":   "—",
                "platform":   "—",
                "identified": False,
            })

    display_results(scan_results, str(network))
    save_report(scan_results, str(network))


# ===========================================================================
# 1. Ping sweep
# ===========================================================================
def ping_sweep(hosts):
    live = []
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Pinging...", total=len(hosts))
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(_ping_host, h): h for h in hosts}
            for f in concurrent.futures.as_completed(futures):
                progress.advance(task)
                if f.result():
                    live.append(futures[f])
    return sorted(live, key=lambda ip: ipaddress.IPv4Address(ip))


def _ping_host(ip):
    try:
        # Windows ping syntax — Linux/macOS users should
        # change -n to -c and -w 500 to -W 1
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(PING_TIMEOUT), ip],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except Exception:
        return False


# ===========================================================================
# 2. SSH port check
# ===========================================================================
def check_ssh_ports(live_hosts):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_check_ssh, h): h for h in live_hosts}
        for f in concurrent.futures.as_completed(futures):
            host = futures[f]
            results[host] = f.result()
    return results


def _check_ssh(ip):
    try:
        with socket.create_connection((ip, SSH_PORT),
                                      timeout=SSH_TIMEOUT):
            return True
    except Exception:
        return False


# ===========================================================================
# 3. Cisco identification
# ===========================================================================
def identify_devices(live_hosts, ssh_results, creds):
    ssh_open   = [h for h in live_hosts if ssh_results.get(h)]
    ssh_closed = [h for h in live_hosts if not ssh_results.get(h)]

    results = []
    for host in ssh_closed:
        results.append({
            "host":       host,
            "alive":      True,
            "ssh_open":   False,
            "hostname":   "—",
            "platform":   "—",
            "identified": False,
        })

    if ssh_open:
        workers = min(10, len(ssh_open))
        with Progress(
            SpinnerColumn(),
            TextColumn("Identifying devices..."),
        ) as progress:
            progress.add_task("", total=None)
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=workers) as ex:
                futures = {
                    ex.submit(_identify_one, h, creds): h
                    for h in ssh_open
                }
                for f in concurrent.futures.as_completed(futures):
                    results.append(f.result())

    return sorted(results,
                  key=lambda r: ipaddress.IPv4Address(r["host"]))


def _identify_one(host, creds):
    try:
        from netmiko import ConnectHandler
        conn_params = {
            "device_type": "cisco_ios",
            "host":        host,
            "username":    creds["username"],
            "password":    creds["password"],
            "secret":      creds["secret"],
            "timeout":     10,
        }
        with ConnectHandler(**conn_params) as conn:
            if creds["secret"]:
                conn.enable()

            ver = conn.send_command("show version")
            platform = "Cisco IOS"
            for line in ver.splitlines():
                if "IOS XE" in line:
                    platform = "Cisco IOS XE"
                    break
                elif "IOS Software" in line:
                    platform = "Cisco IOS"
                    break

            run_host = conn.send_command(
                "show run | include hostname")
            hostname = "unknown"
            for line in run_host.splitlines():
                if line.startswith("hostname"):
                    hostname = line.split()[-1]
                    break

        return {
            "host":       host,
            "alive":      True,
            "ssh_open":   True,
            "hostname":   hostname,
            "platform":   platform,
            "identified": True,
        }
    except Exception:
        return {
            "host":       host,
            "alive":      True,
            "ssh_open":   True,
            "hostname":   "—",
            "platform":   "connection failed",
            "identified": False,
        }


# ===========================================================================
# 4. Display results
# ===========================================================================
def display_results(scan_results, network_str):
    ui.section(f"Scan Results — {network_str}")

    table = Table(title=f"NetScan — {network_str}",
                  header_style="bold cyan",
                  border_style="blue", show_lines=False)
    table.add_column("IP Address", style="cyan",  min_width=16)
    table.add_column("Ping",                       width=8)
    table.add_column("SSH :22",                    width=10)
    table.add_column("Hostname",   style="white",  min_width=20)
    table.add_column("Platform",   style="white",  min_width=16)

    n_alive      = len(scan_results)
    n_ssh        = 0
    n_identified = 0

    for r in scan_results:
        ping_cell = "[green]● alive[/green]"
        if r["ssh_open"]:
            ssh_cell = "[green]● open[/green]"
            n_ssh += 1
        else:
            ssh_cell = "[red]✘ closed[/red]"
        if r["identified"]:
            n_identified += 1
        table.add_row(r["host"], ping_cell, ssh_cell,
                      r["hostname"], r["platform"])

    ui.console.print()
    ui.console.print(table)
    ui.info(
        f"Live: {n_alive} | SSH open: {n_ssh} | "
        f"Cisco identified: {n_identified}"
    )


# ===========================================================================
# 5. Save report
# ===========================================================================
def save_report(scan_results, network_str):
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp    = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_net     = network_str.replace("/", "-").replace(".", "-")
    filename     = OUTPUT_DIR / f"netscan_{safe_net}_{timestamp}.txt"
    ts_full      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    n_alive      = len(scan_results)
    n_ssh        = sum(1 for r in scan_results if r["ssh_open"])
    n_identified = sum(1 for r in scan_results if r["identified"])

    lines = [
        f"! NetScan Report — {network_str}",
        "! Generated by NetForge NetScan v1.0",
        "! built by A. Wassim · github.com/wassimsmt",
        f"! Timestamp: {ts_full}",
        f"! Hosts scanned: {n_alive}",
        f"! Live hosts: {n_alive}",
        f"! SSH open: {n_ssh}",
        f"! Cisco identified: {n_identified}",
        "! " + "─" * 41,
        "",
    ]
    for r in scan_results:
        ssh_str  = "SSH:OPEN  " if r["ssh_open"] else "SSH:CLOSED"
        hostname = r["hostname"]
        platform = r["platform"]
        lines.append(
            f"{r['host']:<18} ALIVE  {ssh_str}  {hostname:<20}  {platform}"
        )

    filename.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ui.ok(f"Report saved: {filename}")
    import netforge_log
    netforge_log.log("NetScan", "Discovery", network_str, "SUCCESS",
                     f"{n_alive} live hosts")
