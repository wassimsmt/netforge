"""
FirstTouch — First-Touch Config (NetForge module)

Bootstraps a factory-default Cisco device from zero to
SSH-ready via console cable, or exports a paste-ready IOS
config block in Simulation mode.

Console mode requires a USB-to-RJ45 console cable and
pyserial. Simulation mode works with Packet Tracer.

built by A. Wassim · github.com/wassimsmt
"""
from getpass import getpass
from pathlib import Path

import ui

OUTPUT_DIR = Path(__file__).parent / "output"


# ===========================================================================
# Entry point
# ===========================================================================
def run():
    ui.section("First-Touch Config")
    mode = connection_menu()
    if mode is None or mode == "back":
        return
    device_type = device_type_menu()
    if device_type is None:
        return
    cfg  = collect_config(device_type)
    cmds = build_command_set(cfg, device_type)
    preview(cfg, cmds)
    if not confirm():
        ui.warn("Cancelled.")
        return
    if mode == "sim":
        export(cfg, cmds)
    else:
        ui.coming_soon("Console cable connection")


# ===========================================================================
# 1. Connection menu
# ===========================================================================
def connection_menu():
    ui.info("Choose a connection method:")
    print(f"  {ui.GREEN}[1]{ui.RESET} Console cable                    {ui.YELLOW}(Coming Soon){ui.RESET}")
    print(f"  {ui.GREEN}[2]{ui.RESET} Simulation / export to file      {ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[99]{ui.RESET} Back to main menu")
    choice = ui.ask(">")
    if choice == "1":
        ui.coming_soon("Console cable connection")
        return None
    if choice == "2":
        return "sim"
    if choice == "99":
        return "back"
    ui.warn("Invalid choice.")
    return None


# ===========================================================================
# 2. Device type menu
# ===========================================================================
def device_type_menu():
    ui.info("What type of device are you configuring?")
    print(f"  {ui.GREEN}[1]{ui.RESET} Switch")
    print(f"  {ui.GREEN}[2]{ui.RESET} Router")
    while True:
        choice = ui.ask(">")
        if choice == "1":
            return "switch"
        if choice == "2":
            return "router"
        ui.warn("Please enter 1 or 2.")


# ===========================================================================
# 3. Collect configuration
# ===========================================================================
def collect_config(device_type):
    cfg = {}
    cfg["device_type"] = device_type

    # A — Device Identity
    ui.section("A — Device Identity")
    cfg["hostname"]         = ui.ask("Hostname:")
    cfg["no_domain_lookup"] = ui.yes_no("no ip domain-lookup?", default=True)

    # B — Security Baseline
    ui.section("B — Security Baseline")
    cfg["enable_secret"] = getpass("Enable secret: ")
    cfg["svc_pw_enc"]    = True
    cfg["banner"]        = ui.ask("Banner text [blank=default]:") or "Authorized Access Only"

    # C — Local User
    ui.section("C — Local User")
    cfg["local_user"]   = ui.ask("Username:")
    cfg["local_secret"] = getpass("User secret: ")

    # D — SSH
    ui.section("D — SSH")
    cfg["domain_name"] = ui.ask("IP domain-name:")
    cfg["rsa_modulus"] = 2048
    cfg["ssh_version"] = 2

    # E — Console Line
    ui.section("E — Console Line")
    cfg["console_password"] = getpass("Console line password: ")

    # F — Management IP
    ui.section("F — Management IP")
    if device_type == "switch":
        cfg["mgmt_vlan"] = ui.ask("Management VLAN ID [default 1]:") or "1"
        cfg["mgmt_ip"]   = ui.ask("Management IP address:")
        cfg["mgmt_mask"] = ui.ask("Subnet mask:")
        cfg["gateway"]   = ui.ask("Default gateway [blank=skip]:")
    else:  # router
        cfg["mgmt_iface"] = ui.ask("Management interface (e.g. Gi0/0):")
        cfg["mgmt_ip"]    = ui.ask("Management IP address:")
        cfg["mgmt_mask"]  = ui.ask("Subnet mask:")
        cfg["gateway"]    = ""

    cfg["save"] = ui.yes_no("Save config (write memory)?", default=True)
    return cfg


# ===========================================================================
# 4. Build IOS command set
# ===========================================================================
def build_command_set(cfg, device_type):
    cmds = []

    # A — Identity
    cmds.append(f"hostname {cfg['hostname']}")
    if cfg["no_domain_lookup"]:
        cmds.append("no ip domain-lookup")

    # B — Security baseline
    cmds.append("service password-encryption")
    cmds.append(f"enable secret {cfg['enable_secret']}")
    cmds.append(f"banner motd #{cfg['banner']}#")

    # C — Local user
    cmds.append(
        f"username {cfg['local_user']} privilege 15 secret {cfg['local_secret']}"
    )

    # D — SSH
    cmds.append(f"ip domain-name {cfg['domain_name']}")
    cmds.append("crypto key generate rsa modulus 2048")
    cmds.append("ip ssh version 2")
    cmds.append("ip ssh time-out 60")
    cmds.append("ip ssh authentication-retries 3")

    # E — VTY lines
    cmds += ["line vty 0 15", "login local", "transport input ssh", "exit"]

    # F — Console line
    cmds += [
        "line console 0",
        f"password {cfg['console_password']}",
        "login",
        "exec-timeout 10 0",
        "exit",
    ]

    # G — Management IP
    if device_type == "switch":
        cmds += [
            f"interface Vlan{cfg['mgmt_vlan']}",
            f"ip address {cfg['mgmt_ip']} {cfg['mgmt_mask']}",
            "no shutdown",
            "exit",
        ]
        if cfg["gateway"]:
            cmds.append(f"ip default-gateway {cfg['gateway']}")
    else:  # router
        cmds += [
            f"interface {cfg['mgmt_iface']}",
            f"ip address {cfg['mgmt_ip']} {cfg['mgmt_mask']}",
            "no shutdown",
            "exit",
        ]

    # H — Save
    if cfg["save"]:
        cmds.append("do write memory")

    return cmds


# ===========================================================================
# 5. Masking, preview, confirm
# ===========================================================================
def _mask(cmd):
    if cmd.startswith("password "):
        return "password ********"
    if cmd.startswith("enable secret "):
        return "enable secret ********"
    if cmd.startswith("username ") and " secret " in cmd:
        idx = cmd.index(" secret ")
        return cmd[:idx + len(" secret ")] + "********"
    if cmd.startswith("banner motd "):
        delim = cmd[len("banner motd "):][:1]
        return f"banner motd {delim}***{delim}"
    return cmd


def preview(cfg, cmds):
    ui.section("Preview")
    print(f"{ui.BRIGHT}{ui.MAGENTA}# {cfg['hostname']}  ({cfg['device_type']}){ui.RESET}")
    for cmd in cmds:
        print(f"   {ui.GREEN}{_mask(cmd)}{ui.RESET}")
    print()
    ui.warn("Review carefully before applying to a factory-default device.")


def confirm():
    print()
    ans = input(
        f"{ui.YELLOW}Apply this configuration? (yes/no) > {ui.RESET}"
    ).strip().lower()
    return ans in ("y", "yes")


# ===========================================================================
# 6. Export to file (Simulation mode)
# ===========================================================================
def export(cfg, cmds):
    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = OUTPUT_DIR / f"first_touch_{cfg['hostname']}.txt"
    lines = [
        f"! First-Touch Config — {cfg['hostname']}",
        "! Generated by NetForge First-Touch v1.0 — built by A. Wassim",
        "! github.com/wassimsmt",
        "! WARNING: Contains plaintext passwords — do not commit",
        "enable",
        "configure terminal",
    ] + cmds + ["end"]
    filename.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ui.ok(f"Written: {filename}")
    ui.warn("File contains plaintext passwords — keep it secure and delete after use.")
