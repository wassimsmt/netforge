"""
ConfigForge — Bulk Config Push (NetForge module)

Connect to one Cisco device or a named series of devices over SSH and push a
standard CCNA-style baseline configuration, after a preview + explicit confirm.

Connection methods:
    SSH ............ ready
    Console cable .. (Coming Soon)

Tested target: GNS3 (IOSv / IOSvL2) with a Cloud/NAT node bridged to the host.
Passwords are read with getpass (never echoed) and masked in the preview.

built by A. Wassim  ·  github.com/wassimsmt
"""
from getpass import getpass
from pathlib import Path

import ui

DEVICE_TYPE = "cisco_ios"          # Netmiko driver for IOS / IOS-XE
BANNER_DELIM = "#"                  # delimiter for 'banner motd'
OUTPUT_DIR = Path(__file__).parent / "output"


# ===========================================================================
# Entry point
# ===========================================================================
def run():
    ui.section("ConfigForge — Bulk Config Push")

    mode = connection_menu()
    if mode in (None, "back"):
        return

    devices = build_inventory()
    if not devices:
        ui.warn("No devices defined. Returning to main menu.")
        return

    cfg = collect_config(need_credentials=(mode == "ssh"))
    plans = [{"name": d["name"], "host": d["host"],
              "commands": build_command_set(d["name"], cfg),
              "sections": cfg["_sections"]} for d in devices]

    preview(plans)

    if mode == "sim":
        export_all(plans)
    else:
        if not confirm():
            ui.warn("Cancelled — nothing was sent.")
            return
        push_all(plans, cfg)


# ===========================================================================
# 1. Connection method
# ===========================================================================
def connection_menu():
    ui.info("Choose a connection method:")
    print(f"  {ui.GREEN}[1]{ui.RESET} SSH            {ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[2]{ui.RESET} Console cable  {ui.YELLOW}(Coming Soon){ui.RESET}")
    print(f"  {ui.GREEN}[3]{ui.RESET} Simulation / Dry-run (export config to file)  "
          f"{ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[99]{ui.RESET} Back to main menu")
    choice = ui.ask(">")
    if choice == "1":
        return "ssh"
    if choice == "2":
        ui.coming_soon("Console cable connection")
        return None
    if choice == "3":
        return "sim"
    if choice == "99":
        return "back"
    ui.warn("Invalid choice.")
    return None


# ===========================================================================
# 2. Inventory (single device or a named series)
# ===========================================================================
def build_inventory():
    ui.section("Inventory")
    ui.info("Configure a single device or a series of devices?")
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
# 3. Configuration to apply (shared across the batch)
# ===========================================================================
def collect_config(need_credentials=True):
    cfg = {}
    cfg["_sections"] = ["Baseline"]

    # --- 1. Device type -------------------------------------------------------
    ui.section("Device Type")
    ui.info("What type of device are you configuring?")
    print(f"  {ui.GREEN}[1]{ui.RESET} Switch")
    print(f"  {ui.GREEN}[2]{ui.RESET} Router")
    print(f"  {ui.GREEN}[3]{ui.RESET} Both")
    while True:
        dt = ui.ask(">")
        if dt == "1":
            cfg["device_type"] = "switch"
            break
        if dt == "2":
            cfg["device_type"] = "router"
            break
        if dt == "3":
            cfg["device_type"] = "both"
            break
        ui.warn("Please enter 1, 2, or 3.")

    # --- 2. Credentials (SSH mode only) ---------------------------------------
    if need_credentials:
        ui.section("Connection credentials (the login that ALREADY exists on the devices)")
        cfg["username"] = ui.ask("SSH username:")
        cfg["password"] = getpass("SSH password: ")
        cfg["secret"] = getpass("Enable secret to log in (blank if none): ")
    else:
        cfg["username"] = cfg["password"] = cfg["secret"] = ""

    # --- 3. Section A — Device Baseline ---------------------------------------
    ui.section("A — Device Baseline")

    cfg["no_domain_lookup"] = ui.yes_no("Add 'no ip domain-lookup'?", default=True)
    cfg["svc_pw_enc"] = ui.yes_no("Add 'service password-encryption'?", default=True)

    if ui.yes_no("Set a NEW 'enable secret'?", default=False):
        cfg["new_enable_secret"] = getpass("New enable secret: ")
    else:
        cfg["new_enable_secret"] = None

    if ui.yes_no("Configure 'line console 0' (password + login)?", default=True):
        cfg["console_password"] = getpass("Console password: ")
    else:
        cfg["console_password"] = None

    if ui.yes_no("Configure 'line vty 0 15' (password + login local)?", default=True):
        cfg["vty_password"] = getpass("VTY password: ")
    else:
        cfg["vty_password"] = None

    if ui.yes_no("Set a 'banner motd'?", default=True):
        text = ui.ask("Banner text (single line):")
        if BANNER_DELIM in text:
            ui.warn(f"Banner can't contain '{BANNER_DELIM}'. Skipping banner.")
            cfg["banner"] = None
        else:
            cfg["banner"] = text
    else:
        cfg["banner"] = None

    shut = ui.ask("Interfaces to SHUTDOWN (comma-separated, e.g. Fa0/1,Gi0/2) [blank=none]:")
    cfg["shutdown_ifaces"] = [s.strip() for s in shut.split(",") if s.strip()]

    enable = ui.ask("Interfaces to ENABLE / no shut (comma-separated) [blank=none]:")
    cfg["enable_ifaces"] = [s.strip() for s in enable.split(",") if s.strip()]

    cfg["save"] = ui.yes_no("Save config (write memory) after applying?", default=True)

    # --- 4. Sections B–O (gated by device type) --------------------------------
    is_switch = cfg["device_type"] in ("switch", "both")
    is_router = cfg["device_type"] in ("router", "both")

    if is_switch:
        _collect_vlans(cfg)
        _collect_access_ports(cfg)
        _collect_trunks(cfg)
        _collect_stp(cfg)
        _collect_etherchannel(cfg)

    _collect_cdp_lldp(cfg)

    if is_router:
        _collect_router_interfaces(cfg)
        _collect_static_routes(cfg)
        _collect_ospf(cfg)
        _collect_dhcp(cfg)
        _collect_nat(cfg)

    _collect_acls(cfg)
    _collect_qos(cfg)
    _collect_security(cfg)

    return cfg


# ---------------------------------------------------------------------------
# Section B — VLANs
# ---------------------------------------------------------------------------
def _collect_vlans(cfg):
    if not ui.yes_no("Configure VLANs?", default=False):
        cfg["vlans"] = None
        return
    cfg["_sections"].append("VLANs")
    count = ui.int_prompt("How many VLANs to create", default=1)
    vlan_list = []
    for i in range(count):
        vid = ui.ask(f"VLAN {i + 1} ID:")
        vname = ui.ask(f"VLAN {i + 1} name [blank=skip]:")
        vlan_list.append({"id": vid, "name": vname})

    svi = None
    if ui.yes_no("Configure a management SVI?", default=False):
        svi = {
            "vlan": ui.ask("SVI VLAN ID:"),
            "ip":   ui.ask("IP address:"),
            "mask": ui.ask("Subnet mask:"),
        }

    gw = None
    if ui.yes_no("Set a default gateway?", default=False):
        gw = ui.ask("Gateway IP:")

    cfg["vlans"] = {"list": vlan_list, "svi": svi, "gateway": gw}


# ---------------------------------------------------------------------------
# Section C — Access Ports
# ---------------------------------------------------------------------------
def _collect_access_ports(cfg):
    if not ui.yes_no("Configure access ports?", default=False):
        cfg["access_ports"] = None
        return
    cfg["_sections"].append("Access Ports")
    count = ui.int_prompt("How many access ports to configure", default=1)
    ports = []
    for i in range(count):
        iface = ui.ask(f"Port {i + 1} interface (e.g. Gi0/1):")
        vlan  = ui.ask("Access VLAN ID:")
        voice = ui.ask("Voice VLAN ID [blank=skip]:")
        shut  = ui.yes_no("Shutdown this port?", default=False)
        ports.append({"iface": iface, "vlan": vlan, "voice": voice, "shut": shut})
    cfg["access_ports"] = ports


# ---------------------------------------------------------------------------
# Section D — Trunking
# ---------------------------------------------------------------------------
def _collect_trunks(cfg):
    if not ui.yes_no("Configure trunk ports?", default=False):
        cfg["trunk_ports"] = None
        return
    cfg["_sections"].append("Trunking")
    count = ui.int_prompt("How many trunk ports", default=1)
    ports = []
    for i in range(count):
        iface   = ui.ask(f"Trunk port {i + 1} interface:")
        enc     = ui.yes_no("Set encapsulation dot1q?", default=True)
        native  = ui.ask("Native VLAN [blank=skip]:")
        allowed = ui.ask("Allowed VLANs (e.g. 10,20,30) [blank=all]:")
        ports.append({"iface": iface, "encap": enc,
                      "native": native, "allowed": allowed})
    cfg["trunk_ports"] = ports


# ---------------------------------------------------------------------------
# Section E — Spanning Tree
# ---------------------------------------------------------------------------
def _collect_stp(cfg):
    if not ui.yes_no("Configure Spanning Tree?", default=False):
        cfg["stp"] = None
        return
    cfg["_sections"].append("STP")
    stp = {}

    ui.info("STP mode: [1] pvst  [2] rapid-pvst  (default: 2)")
    mode_ch = ui.ask(">")
    stp["mode"] = "pvst" if mode_ch == "1" else "rapid-pvst"

    stp["root"] = None
    if ui.yes_no("Set root bridge for specific VLANs?", default=False):
        vlans = ui.ask("VLANs (e.g. 10,20):")
        ui.info("[1] primary  [2] secondary")
        rc = ui.ask(">")
        stp["root"] = {"vlans": vlans,
                       "type": "secondary" if rc == "2" else "primary"}

    stp["priority"] = None
    if ui.yes_no("Set bridge priority manually?", default=False):
        vlans = ui.ask("VLAN list:")
        pri   = ui.int_prompt("Priority (multiple of 4096, default 32768)", default=32768)
        stp["priority"] = {"vlans": vlans, "value": pri}

    stp["portfast_global"]  = ui.yes_no("Enable PortFast globally?", default=False)
    stp["bpduguard_global"] = ui.yes_no("Enable BPDU Guard globally?", default=False)

    stp["iface_stp"] = []
    if ui.yes_no("Enable PortFast/BPDU Guard on specific interfaces?", default=False):
        n = ui.int_prompt("How many interfaces", default=1)
        for _ in range(n):
            iface = ui.ask("Interface:")
            pf    = ui.yes_no("PortFast?", default=True)
            bg    = ui.yes_no("BPDU Guard?", default=True)
            stp["iface_stp"].append({"iface": iface, "portfast": pf, "bpduguard": bg})

    cfg["stp"] = stp


# ---------------------------------------------------------------------------
# Section F — EtherChannel
# ---------------------------------------------------------------------------
def _collect_etherchannel(cfg):
    if not ui.yes_no("Configure EtherChannel?", default=False):
        cfg["etherchannel"] = None
        return
    cfg["_sections"].append("EtherChannel")
    count = ui.int_prompt("How many EtherChannel groups", default=1)
    groups = []
    for i in range(count):
        grp_num = ui.ask(f"Channel group {i + 1} number:")
        ui.info("Protocol: [1] LACP  [2] PAgP  [3] Static")
        proto_ch = ui.ask(">")
        if proto_ch == "1":
            proto = "lacp"
            ui.info("Mode: active / passive")
            mode = ui.ask("Mode:")
        elif proto_ch == "2":
            proto = "pagp"
            ui.info("Mode: desirable / auto")
            mode = ui.ask("Mode:")
        else:
            proto = "static"
            mode  = "on"
        members_raw = ui.ask("Member interfaces (comma-separated):")
        members = [m.strip() for m in members_raw.split(",") if m.strip()]
        trunk   = ui.yes_no("Configure Port-channel as trunk?", default=False)
        native = allowed = ""
        if trunk:
            native  = ui.ask("Native VLAN [blank=skip]:")
            allowed = ui.ask("Allowed VLANs [blank=all]:")
        groups.append({"num": grp_num, "proto": proto, "mode": mode,
                       "members": members, "trunk": trunk,
                       "native": native, "allowed": allowed})
    cfg["etherchannel"] = groups


# ---------------------------------------------------------------------------
# Section G — CDP / LLDP
# ---------------------------------------------------------------------------
def _collect_cdp_lldp(cfg):
    if not ui.yes_no("Configure CDP/LLDP?", default=False):
        cfg["cdp_lldp"] = None
        return
    cfg["_sections"].append("CDP/LLDP")
    c = {}

    c["cdp_run"] = ui.yes_no("Enable CDP globally?", default=True)
    c["cdp_disable_ifaces"] = []
    if ui.yes_no("Disable CDP on specific interfaces?", default=False):
        raw = ui.ask("Interfaces (comma-separated):")
        c["cdp_disable_ifaces"] = [x.strip() for x in raw.split(",") if x.strip()]

    c["lldp_run"] = ui.yes_no("Enable LLDP globally?", default=True)
    c["lldp_disable_ifaces"] = []
    if ui.yes_no("Disable LLDP transmit on specific interfaces?", default=False):
        raw = ui.ask("Interfaces (comma-separated):")
        c["lldp_disable_ifaces"] = [x.strip() for x in raw.split(",") if x.strip()]

    cfg["cdp_lldp"] = c


# ---------------------------------------------------------------------------
# Section H — Router Interfaces & IP
# ---------------------------------------------------------------------------
def _collect_router_interfaces(cfg):
    if not ui.yes_no("Configure router interfaces?", default=False):
        cfg["router_ifaces"] = None
        return
    cfg["_sections"].append("Router Interfaces")
    count = ui.int_prompt("How many interfaces to configure", default=1)
    ifaces = []
    for i in range(count):
        iface = ui.ask(f"Interface {i + 1} (e.g. Gi0/0):")
        desc  = ui.ask("Description [blank=skip]:")
        ip    = ui.ask("IP address [blank=skip]:")
        mask  = ui.ask("Subnet mask:") if ip else ""
        ipv6  = ui.ask("IPv6 address (e.g. 2001:db8::1/64) [blank=skip]:")
        shut  = ui.yes_no("Shutdown?", default=False)
        ifaces.append({"iface": iface, "desc": desc,
                       "ip": ip, "mask": mask, "ipv6": ipv6, "shut": shut})

    sub_ifaces = []
    if ui.yes_no("Configure sub-interfaces (Router-on-a-Stick)?", default=False):
        n = ui.int_prompt("How many sub-interfaces", default=1)
        for _ in range(n):
            parent  = ui.ask("Parent interface (e.g. Gi0/0):")
            sub_num = ui.ask("Sub-interface number:")
            vlan    = ui.ask("VLAN ID:")
            ip      = ui.ask("IP address:")
            mask    = ui.ask("Subnet mask:")
            sub_ifaces.append({"parent": parent, "num": sub_num,
                                "vlan": vlan, "ip": ip, "mask": mask})

    cfg["router_ifaces"] = {"ifaces": ifaces, "sub_ifaces": sub_ifaces}


# ---------------------------------------------------------------------------
# Section I — Static Routing
# ---------------------------------------------------------------------------
def _collect_static_routes(cfg):
    if not ui.yes_no("Configure static routes?", default=False):
        cfg["static_routes"] = None
        return
    cfg["_sections"].append("Static Routing")
    routes = {"default": None, "ipv4": [], "ipv6": []}

    if ui.yes_no("Add a default route?", default=False):
        routes["default"] = ui.ask("Next-hop IP or exit interface:")

    if ui.yes_no("Add IPv4 static routes?", default=False):
        n = ui.int_prompt("How many", default=1)
        for _ in range(n):
            net = ui.ask("Destination network:")
            mask = ui.ask("Subnet mask:")
            nh  = ui.ask("Next-hop:")
            ad  = ui.ask("Administrative distance [blank=default]:")
            routes["ipv4"].append({"net": net, "mask": mask, "nexthop": nh, "ad": ad})

    if ui.yes_no("Add IPv6 static routes?", default=False):
        n = ui.int_prompt("How many", default=1)
        for _ in range(n):
            dest = ui.ask("Destination (e.g. 2001:db8::/32):")
            nh   = ui.ask("Next-hop:")
            routes["ipv6"].append({"dest": dest, "nexthop": nh})

    cfg["static_routes"] = routes


# ---------------------------------------------------------------------------
# Section J — OSPF
# ---------------------------------------------------------------------------
def _collect_ospf(cfg):
    if not ui.yes_no("Configure OSPF?", default=False):
        cfg["ospf"] = None
        return
    cfg["_sections"].append("OSPF")
    ospf = {}

    ospf["pid"]       = ui.int_prompt("OSPF process ID", default=1)
    ospf["router_id"] = ui.ask("Router ID [blank=skip]:")

    ospf["networks"] = []
    if ui.yes_no("Add network statements?", default=True):
        n = ui.int_prompt("How many", default=1)
        for _ in range(n):
            net  = ui.ask("Network address:")
            wild = ui.ask("Wildcard mask:")
            area = ui.ask("Area (default 0):") or "0"
            ospf["networks"].append({"net": net, "wild": wild, "area": area})

    ospf["passive"] = []
    if ui.yes_no("Set passive interfaces?", default=False):
        raw = ui.ask("Interfaces (comma-separated):")
        ospf["passive"] = [x.strip() for x in raw.split(",") if x.strip()]

    ospf["default_originate"] = ui.yes_no("Advertise default route?", default=False)

    ospf["costs"] = []
    if ui.yes_no("Set OSPF cost on interfaces?", default=False):
        n = ui.int_prompt("How many interfaces", default=1)
        for _ in range(n):
            iface = ui.ask("Interface:")
            cost  = ui.ask("Cost:")
            ospf["costs"].append({"iface": iface, "cost": cost})

    cfg["ospf"] = ospf


# ---------------------------------------------------------------------------
# Section K — DHCP Server
# ---------------------------------------------------------------------------
def _collect_dhcp(cfg):
    if not ui.yes_no("Configure DHCP server?", default=False):
        cfg["dhcp"] = None
        return
    cfg["_sections"].append("DHCP Server")
    dhcp = {"excluded": [], "pools": []}

    if ui.yes_no("Excluded address ranges?", default=False):
        n = ui.int_prompt("How many ranges", default=1)
        for _ in range(n):
            start = ui.ask("Start IP:")
            end   = ui.ask("End IP [blank=single]:")
            dhcp["excluded"].append({"start": start, "end": end})

    count = ui.int_prompt("How many DHCP pools", default=1)
    for _ in range(count):
        name  = ui.ask("Pool name:")
        net   = ui.ask("Network address:")
        mask  = ui.ask("Subnet mask:")
        gw    = ui.ask("Default gateway [blank=skip]:")
        dns   = ui.ask("DNS server [blank=skip]:")
        lease = ui.int_prompt("Lease days", default=1)
        dhcp["pools"].append({"name": name, "net": net, "mask": mask,
                               "gw": gw, "dns": dns, "lease": lease})

    cfg["dhcp"] = dhcp


# ---------------------------------------------------------------------------
# Section L — NAT
# ---------------------------------------------------------------------------
def _collect_nat(cfg):
    if not ui.yes_no("Configure NAT?", default=False):
        cfg["nat"] = None
        return
    cfg["_sections"].append("NAT")
    nat = {}

    ui.info("NAT type: [1] Static  [2] Dynamic  [3] PAT (overload)")
    nat_ch = ui.ask(">")
    nat["type"] = {"1": "static", "2": "dynamic"}.get(nat_ch, "pat")

    nat["inside"]  = ui.ask("Inside interface (e.g. Gi0/0):")
    nat["outside"] = ui.ask("Outside interface (e.g. Gi0/1):")

    if nat["type"] == "static":
        nat["local_ip"]  = ui.ask("Local IP:")
        nat["global_ip"] = ui.ask("Global IP:")
    elif nat["type"] == "dynamic":
        nat["pool_name"]    = ui.ask("Pool name:")
        nat["pool_start"]   = ui.ask("Pool start IP:")
        nat["pool_end"]     = ui.ask("Pool end IP:")
        nat["pool_netmask"] = ui.ask("Pool netmask:")
        nat["acl"]          = ui.ask("ACL number for interesting traffic:")
    else:  # pat
        nat["acl"]         = ui.ask("ACL number for interesting traffic:")
        nat["use_outside"] = ui.yes_no("Use outside interface?", default=True)
        if not nat["use_outside"]:
            nat["pool_name"]    = ui.ask("Pool name:")
            nat["pool_start"]   = ui.ask("Pool start IP:")
            nat["pool_end"]     = ui.ask("Pool end IP:")
            nat["pool_netmask"] = ui.ask("Pool netmask:")

    cfg["nat"] = nat


# ---------------------------------------------------------------------------
# Section M — ACLs
# ---------------------------------------------------------------------------
def _collect_acls(cfg):
    if not ui.yes_no("Configure ACLs?", default=False):
        cfg["acls"] = None
        return
    cfg["_sections"].append("ACLs")
    count = ui.int_prompt("How many ACLs", default=1)
    acls = []

    for i in range(count):
        ui.info(f"ACL {i + 1} — Type: [1] Standard numbered  [2] Extended numbered  "
                f"[3] Named standard  [4] Named extended")
        acl_type_ch = ui.ask(">")
        acl = {}

        if acl_type_ch == "1":
            acl["type"] = "std_num"
            acl["num"]  = ui.ask("ACL number (1-99):")
            n_e = ui.int_prompt("How many entries", default=1)
            acl["entries"] = []
            for _ in range(n_e):
                action = ui.ask("permit or deny:")
                src    = ui.ask("Source IP:")
                wild   = ui.ask("Wildcard [blank=host]:")
                acl["entries"].append({"action": action, "src": src, "wild": wild})

        elif acl_type_ch == "2":
            acl["type"] = "ext_num"
            acl["num"]  = ui.ask("ACL number (100-199):")
            n_e = ui.int_prompt("How many entries", default=1)
            acl["entries"] = []
            for _ in range(n_e):
                action = ui.ask("permit/deny:")
                proto  = ui.ask("Protocol (ip/tcp/udp/icmp):")
                src    = ui.ask("Source IP:")
                swild  = ui.ask("Source wildcard:")
                dst    = ui.ask("Destination IP:")
                dwild  = ui.ask("Destination wildcard:")
                port   = ui.ask("Port (e.g. eq 80) [blank=skip]:")
                acl["entries"].append({"action": action, "proto": proto,
                                       "src": src, "swild": swild,
                                       "dst": dst, "dwild": dwild, "port": port})

        elif acl_type_ch == "3":
            acl["type"] = "named_std"
            acl["name"] = ui.ask("ACL name:")
            n_e = ui.int_prompt("How many entries", default=1)
            acl["entries"] = []
            for _ in range(n_e):
                action = ui.ask("permit or deny:")
                src    = ui.ask("Source IP:")
                wild   = ui.ask("Wildcard [blank=host]:")
                acl["entries"].append({"action": action, "src": src, "wild": wild})

        else:
            acl["type"] = "named_ext"
            acl["name"] = ui.ask("ACL name:")
            n_e = ui.int_prompt("How many entries", default=1)
            acl["entries"] = []
            for _ in range(n_e):
                action = ui.ask("permit/deny:")
                proto  = ui.ask("Protocol (ip/tcp/udp/icmp):")
                src    = ui.ask("Source IP:")
                swild  = ui.ask("Source wildcard:")
                dst    = ui.ask("Destination IP:")
                dwild  = ui.ask("Destination wildcard:")
                port   = ui.ask("Port (e.g. eq 80) [blank=skip]:")
                acl["entries"].append({"action": action, "proto": proto,
                                       "src": src, "swild": swild,
                                       "dst": dst, "dwild": dwild, "port": port})

        acl["apply_iface"] = None
        if ui.yes_no("Apply to an interface?", default=False):
            iface = ui.ask("Interface:")
            ui.info("[1] in  [2] out")
            dir_ch = ui.ask(">")
            acl["apply_iface"] = {"iface": iface,
                                  "direction": "out" if dir_ch == "2" else "in"}

        acl["apply_vty"] = ui.yes_no("Apply to VTY lines?", default=False)
        acls.append(acl)

    cfg["acls"] = acls


# ---------------------------------------------------------------------------
# Section N — QoS
# ---------------------------------------------------------------------------
def _collect_qos(cfg):
    if not ui.yes_no("Configure QoS?", default=False):
        cfg["qos"] = None
        return
    cfg["_sections"].append("QoS")
    q = {}

    q["mls_qos"] = ui.yes_no("Enable QoS globally?", default=True)
    q["trust_ifaces"] = []
    if ui.yes_no("Set trust state on interfaces?", default=False):
        n = ui.int_prompt("How many interfaces", default=1)
        for _ in range(n):
            iface = ui.ask("Interface:")
            ui.info("Trust: [1] dscp  [2] cos")
            trust_ch = ui.ask(">")
            trust = "cos" if trust_ch == "2" else "dscp"
            q["trust_ifaces"].append({"iface": iface, "trust": trust})

    cfg["qos"] = q


# ---------------------------------------------------------------------------
# Section O — Security Hardening
# ---------------------------------------------------------------------------
def _collect_security(cfg):
    if not ui.yes_no("Configure security hardening?", default=False):
        cfg["security"] = None
        return
    cfg["_sections"].append("Security Hardening")
    sec = {}

    sec["port_security"] = []
    if ui.yes_no("Enable port security on interfaces?", default=False):
        n = ui.int_prompt("How many interfaces", default=1)
        for _ in range(n):
            iface   = ui.ask("Interface:")
            max_mac = ui.int_prompt("Max MACs", default=1)
            ui.info("Violation mode: [1] shutdown  [2] restrict  [3] protect")
            v_ch = ui.ask(">")
            vmode = {"2": "restrict", "3": "protect"}.get(v_ch, "shutdown")
            sticky = ui.yes_no("Sticky MAC?", default=True)
            sec["port_security"].append({"iface": iface, "max": max_mac,
                                         "mode": vmode, "sticky": sticky})

    sec["ssh_harden"]       = ui.yes_no("Harden SSH?", default=True)
    sec["no_http"]          = ui.yes_no("Disable HTTP server?", default=False)
    sec["no_small_services"] = ui.yes_no("Disable unused small services?", default=False)

    cfg["security"] = sec


# ===========================================================================
# 4. Build the IOS command list for one device
# ===========================================================================
def build_command_set(name, cfg):
    cmds = _build_baseline(name, cfg)
    cmds += _build_vlans(cfg)
    cmds += _build_access_ports(cfg)
    cmds += _build_trunks(cfg)
    cmds += _build_stp(cfg)
    cmds += _build_etherchannel(cfg)
    cmds += _build_cdp_lldp(cfg)
    cmds += _build_router_interfaces(cfg)
    cmds += _build_static_routes(cfg)
    cmds += _build_ospf(cfg)
    cmds += _build_dhcp(cfg)
    cmds += _build_nat(cfg)
    cmds += _build_acls(cfg)
    cmds += _build_qos(cfg)
    cmds += _build_security(cfg)
    return cmds


# ---------------------------------------------------------------------------
# Section A builder
# ---------------------------------------------------------------------------
def _build_baseline(name, cfg):
    cmds = [f"hostname {name}"]

    if cfg["no_domain_lookup"]:
        cmds.append("no ip domain-lookup")

    if cfg.get("svc_pw_enc"):
        cmds.append("service password-encryption")

    if cfg["new_enable_secret"]:
        cmds.append(f"enable secret {cfg['new_enable_secret']}")

    if cfg["console_password"]:
        cmds += ["line console 0",
                 f"password {cfg['console_password']}",
                 "login",
                 "exit"]

    if cfg["vty_password"]:
        cmds += ["line vty 0 15",
                 f"password {cfg['vty_password']}",
                 "login local",
                 "exit"]

    if cfg["banner"]:
        cmds.append(f"banner motd {BANNER_DELIM}{cfg['banner']}{BANNER_DELIM}")

    for iface in cfg["shutdown_ifaces"]:
        cmds += [f"interface {iface}", "shutdown", "exit"]

    for iface in cfg["enable_ifaces"]:
        cmds += [f"interface {iface}", "no shutdown", "exit"]

    return cmds


# ---------------------------------------------------------------------------
# Section B builder — VLANs
# ---------------------------------------------------------------------------
def _build_vlans(cfg):
    if not cfg.get("vlans"):
        return []
    cmds = []
    v = cfg["vlans"]

    for vlan in v["list"]:
        cmds.append(f"vlan {vlan['id']}")
        if vlan["name"]:
            cmds.append(f"name {vlan['name']}")
        cmds.append("exit")

    if v["svi"]:
        svi = v["svi"]
        cmds += [f"interface Vlan{svi['vlan']}",
                 f"ip address {svi['ip']} {svi['mask']}",
                 "no shutdown",
                 "exit"]

    if v["gateway"]:
        cmds.append(f"ip default-gateway {v['gateway']}")

    return cmds


# ---------------------------------------------------------------------------
# Section C builder — Access Ports
# ---------------------------------------------------------------------------
def _build_access_ports(cfg):
    if not cfg.get("access_ports"):
        return []
    cmds = []

    for p in cfg["access_ports"]:
        cmds += [f"interface {p['iface']}",
                 "switchport mode access",
                 f"switchport access vlan {p['vlan']}"]
        if p["voice"]:
            cmds.append(f"switchport voice vlan {p['voice']}")
        cmds.append("shutdown" if p["shut"] else "no shutdown")
        cmds.append("exit")

    return cmds


# ---------------------------------------------------------------------------
# Section D builder — Trunking
# ---------------------------------------------------------------------------
def _build_trunks(cfg):
    if not cfg.get("trunk_ports"):
        return []
    cmds = []

    for p in cfg["trunk_ports"]:
        cmds.append(f"interface {p['iface']}")
        if p["encap"]:
            cmds.append("switchport trunk encapsulation dot1q")
        cmds.append("switchport mode trunk")
        if p["native"]:
            cmds.append(f"switchport trunk native vlan {p['native']}")
        if p["allowed"]:
            cmds.append(f"switchport trunk allowed vlan {p['allowed']}")
        cmds.append("exit")

    return cmds


# ---------------------------------------------------------------------------
# Section E builder — STP
# ---------------------------------------------------------------------------
def _build_stp(cfg):
    if not cfg.get("stp"):
        return []
    cmds = []
    s = cfg["stp"]

    cmds.append(f"spanning-tree mode {s['mode']}")

    if s["root"]:
        cmds.append(f"spanning-tree vlan {s['root']['vlans']} root {s['root']['type']}")

    if s["priority"]:
        cmds.append(f"spanning-tree vlan {s['priority']['vlans']} "
                    f"priority {s['priority']['value']}")

    if s["portfast_global"]:
        cmds.append("spanning-tree portfast default")

    if s["bpduguard_global"]:
        cmds.append("spanning-tree portfast bpduguard default")

    for entry in s["iface_stp"]:
        cmds.append(f"interface {entry['iface']}")
        if entry["portfast"]:
            cmds.append("spanning-tree portfast")
        if entry["bpduguard"]:
            cmds.append("spanning-tree bpduguard enable")
        cmds.append("exit")

    return cmds


# ---------------------------------------------------------------------------
# Section F builder — EtherChannel
# ---------------------------------------------------------------------------
def _build_etherchannel(cfg):
    if not cfg.get("etherchannel"):
        return []
    cmds = []

    for g in cfg["etherchannel"]:
        for member in g["members"]:
            cmds += [f"interface {member}",
                     f"channel-group {g['num']} mode {g['mode']}",
                     "exit"]
        cmds.append(f"interface Port-channel{g['num']}")
        if g["trunk"]:
            cmds += ["switchport trunk encapsulation dot1q",
                     "switchport mode trunk"]
            if g["native"]:
                cmds.append(f"switchport trunk native vlan {g['native']}")
            if g["allowed"]:
                cmds.append(f"switchport trunk allowed vlan {g['allowed']}")
        cmds.append("exit")

    return cmds


# ---------------------------------------------------------------------------
# Section G builder — CDP / LLDP
# ---------------------------------------------------------------------------
def _build_cdp_lldp(cfg):
    if not cfg.get("cdp_lldp"):
        return []
    cmds = []
    c = cfg["cdp_lldp"]

    cmds.append("cdp run" if c["cdp_run"] else "no cdp run")

    for iface in c["cdp_disable_ifaces"]:
        cmds += [f"interface {iface}", "no cdp enable", "exit"]

    cmds.append("lldp run" if c["lldp_run"] else "no lldp run")

    for iface in c["lldp_disable_ifaces"]:
        cmds += [f"interface {iface}", "no lldp transmit", "no lldp receive", "exit"]

    return cmds


# ---------------------------------------------------------------------------
# Section H builder — Router Interfaces
# ---------------------------------------------------------------------------
def _build_router_interfaces(cfg):
    if not cfg.get("router_ifaces"):
        return []
    cmds = []
    r = cfg["router_ifaces"]

    for iface in r["ifaces"]:
        cmds.append(f"interface {iface['iface']}")
        if iface["desc"]:
            cmds.append(f"description {iface['desc']}")
        if iface["ip"]:
            cmds.append(f"ip address {iface['ip']} {iface['mask']}")
        if iface["ipv6"]:
            cmds.append(f"ipv6 address {iface['ipv6']}")
        cmds.append("shutdown" if iface["shut"] else "no shutdown")
        cmds.append("exit")

    for sub in r["sub_ifaces"]:
        cmds += [f"interface {sub['parent']}.{sub['num']}",
                 f"encapsulation dot1Q {sub['vlan']}",
                 f"ip address {sub['ip']} {sub['mask']}",
                 "exit"]

    return cmds


# ---------------------------------------------------------------------------
# Section I builder — Static Routing
# ---------------------------------------------------------------------------
def _build_static_routes(cfg):
    if not cfg.get("static_routes"):
        return []
    cmds = []
    r = cfg["static_routes"]

    if r["default"]:
        cmds.append(f"ip route 0.0.0.0 0.0.0.0 {r['default']}")

    for route in r["ipv4"]:
        cmd = f"ip route {route['net']} {route['mask']} {route['nexthop']}"
        if route["ad"]:
            cmd += f" {route['ad']}"
        cmds.append(cmd)

    for route in r["ipv6"]:
        cmds.append(f"ipv6 route {route['dest']} {route['nexthop']}")

    return cmds


# ---------------------------------------------------------------------------
# Section J builder — OSPF
# ---------------------------------------------------------------------------
def _build_ospf(cfg):
    if not cfg.get("ospf"):
        return []
    cmds = []
    o = cfg["ospf"]

    cmds.append(f"router ospf {o['pid']}")

    if o["router_id"]:
        cmds.append(f"router-id {o['router_id']}")

    for net in o["networks"]:
        cmds.append(f"network {net['net']} {net['wild']} area {net['area']}")

    for iface in o["passive"]:
        cmds.append(f"passive-interface {iface}")

    if o["default_originate"]:
        cmds.append("default-information originate")

    cmds.append("exit")

    for cost in o["costs"]:
        cmds += [f"interface {cost['iface']}",
                 f"ip ospf cost {cost['cost']}",
                 "exit"]

    return cmds


# ---------------------------------------------------------------------------
# Section K builder — DHCP Server
# ---------------------------------------------------------------------------
def _build_dhcp(cfg):
    if not cfg.get("dhcp"):
        return []
    cmds = []
    d = cfg["dhcp"]

    for ex in d["excluded"]:
        if ex["end"]:
            cmds.append(f"ip dhcp excluded-address {ex['start']} {ex['end']}")
        else:
            cmds.append(f"ip dhcp excluded-address {ex['start']}")

    for pool in d["pools"]:
        cmds += [f"ip dhcp pool {pool['name']}",
                 f"network {pool['net']} {pool['mask']}"]
        if pool["gw"]:
            cmds.append(f"default-router {pool['gw']}")
        if pool["dns"]:
            cmds.append(f"dns-server {pool['dns']}")
        cmds += [f"lease {pool['lease']}", "exit"]

    return cmds


# ---------------------------------------------------------------------------
# Section L builder — NAT
# ---------------------------------------------------------------------------
def _build_nat(cfg):
    if not cfg.get("nat"):
        return []
    cmds = []
    n = cfg["nat"]

    cmds += [f"interface {n['inside']}", "ip nat inside", "exit"]
    cmds += [f"interface {n['outside']}", "ip nat outside", "exit"]

    if n["type"] == "static":
        cmds.append(f"ip nat inside source static {n['local_ip']} {n['global_ip']}")
    elif n["type"] == "dynamic":
        cmds += [f"ip nat pool {n['pool_name']} {n['pool_start']} {n['pool_end']} "
                 f"netmask {n['pool_netmask']}",
                 f"ip nat inside source list {n['acl']} pool {n['pool_name']}"]
    else:  # pat
        if n["use_outside"]:
            cmds.append(f"ip nat inside source list {n['acl']} "
                        f"interface {n['outside']} overload")
        else:
            cmds += [f"ip nat pool {n['pool_name']} {n['pool_start']} {n['pool_end']} "
                     f"netmask {n['pool_netmask']}",
                     f"ip nat inside source list {n['acl']} "
                     f"pool {n['pool_name']} overload"]

    return cmds


# ---------------------------------------------------------------------------
# Section M builder — ACLs
# ---------------------------------------------------------------------------
def _build_acls(cfg):
    if not cfg.get("acls"):
        return []
    cmds = []

    for acl in cfg["acls"]:
        acl_id = acl.get("num") or acl.get("name")

        if acl["type"] == "std_num":
            for e in acl["entries"]:
                if e["wild"]:
                    cmds.append(f"access-list {acl_id} {e['action']} "
                                f"{e['src']} {e['wild']}")
                else:
                    cmds.append(f"access-list {acl_id} {e['action']} host {e['src']}")

        elif acl["type"] == "ext_num":
            for e in acl["entries"]:
                cmd = (f"access-list {acl_id} {e['action']} {e['proto']} "
                       f"{e['src']} {e['swild']} {e['dst']} {e['dwild']}")
                if e["port"]:
                    cmd += f" {e['port']}"
                cmds.append(cmd)

        elif acl["type"] == "named_std":
            cmds.append(f"ip access-list standard {acl_id}")
            for e in acl["entries"]:
                if e["wild"]:
                    cmds.append(f"{e['action']} {e['src']} {e['wild']}")
                else:
                    cmds.append(f"{e['action']} host {e['src']}")
            cmds.append("exit")

        else:  # named_ext
            cmds.append(f"ip access-list extended {acl_id}")
            for e in acl["entries"]:
                cmd = (f"{e['action']} {e['proto']} "
                       f"{e['src']} {e['swild']} {e['dst']} {e['dwild']}")
                if e["port"]:
                    cmd += f" {e['port']}"
                cmds.append(cmd)
            cmds.append("exit")

        if acl.get("apply_iface"):
            ai = acl["apply_iface"]
            cmds += [f"interface {ai['iface']}",
                     f"ip access-group {acl_id} {ai['direction']}",
                     "exit"]

        if acl.get("apply_vty"):
            cmds += ["line vty 0 15",
                     f"access-class {acl_id} in",
                     "exit"]

    return cmds


# ---------------------------------------------------------------------------
# Section N builder — QoS
# ---------------------------------------------------------------------------
def _build_qos(cfg):
    if not cfg.get("qos"):
        return []
    cmds = []
    q = cfg["qos"]

    if q["mls_qos"]:
        cmds.append("mls qos")

    for ti in q["trust_ifaces"]:
        cmds += [f"interface {ti['iface']}",
                 f"mls qos trust {ti['trust']}",
                 "exit"]

    return cmds


# ---------------------------------------------------------------------------
# Section O builder — Security Hardening
# ---------------------------------------------------------------------------
def _build_security(cfg):
    if not cfg.get("security"):
        return []
    cmds = []
    s = cfg["security"]

    for ps in s["port_security"]:
        cmds += [f"interface {ps['iface']}",
                 "switchport mode access",
                 "switchport port-security",
                 f"switchport port-security maximum {ps['max']}",
                 f"switchport port-security violation {ps['mode']}"]
        if ps["sticky"]:
            cmds.append("switchport port-security mac-address sticky")
        cmds.append("exit")

    if s["ssh_harden"]:
        cmds += ["ip ssh version 2",
                 "ip ssh time-out 60",
                 "ip ssh authentication-retries 3"]

    if s["no_http"]:
        cmds += ["no ip http server",
                 "no ip http secure-server"]

    if s["no_small_services"]:
        cmds += ["no service tcp-small-servers",
                 "no service udp-small-servers"]

    return cmds


# ===========================================================================
# 5. Preview (passwords masked) + confirm
# ===========================================================================
def _mask(cmd):
    for kw in ("password ", "enable secret "):
        if cmd.startswith(kw):
            return kw + "********"
    return cmd


def preview(plans):
    ui.section("Preview — the following will be sent")
    for p in plans:
        print(f"{ui.BRIGHT}{ui.MAGENTA}# {p['name']}  ({p['host']}){ui.RESET}")
        for c in p["commands"]:
            print(f"   {ui.GREEN}{_mask(c)}{ui.RESET}")
        print()
    ui.warn("Note: changing the vty password/login affects only NEW SSH sessions, "
            "so your current session stays up while pushing.")


def confirm():
    print()
    ans = input(f"{ui.YELLOW}Apply this configuration to all devices? (yes/no) > "
                f"{ui.RESET}").strip().lower()
    return ans in ("y", "yes")


# ===========================================================================
# 6. Export to file (Simulation / dry-run mode)
# ===========================================================================
def export_all(plans):
    OUTPUT_DIR.mkdir(exist_ok=True)
    ui.section("Exporting configuration files")
    for p in plans:
        path = OUTPUT_DIR / f"{p['name']}.txt"
        sections_str = ", ".join(p.get("sections", ["Baseline"]))
        lines = [
            f"! {p['name']}  ({p['host']})",
            f"! Sections: {sections_str}",
            "! Generated by NetForge ConfigForge v1.0 — built by A. Wassim",
            "! github.com/wassimsmt",
            "enable",
            "configure terminal",
        ] + p["commands"] + ["end"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ui.ok(f"Written: {path}")
    ui.warn("These files contain plaintext passwords — do not commit them to version control.")


# ===========================================================================
# 7. Push over SSH (Netmiko)
# ===========================================================================
def push_all(plans, cfg):
    try:
        from netmiko import (ConnectHandler,
                             NetmikoTimeoutException,
                             NetmikoAuthenticationException)
    except ImportError:
        ui.error("Netmiko is not installed. Run:  pip install -r requirements.txt")
        return

    ui.section("Applying configuration")
    results = []

    for p in plans:
        device = {
            "device_type": DEVICE_TYPE,
            "host": p["host"],
            "username": cfg["username"],
            "password": cfg["password"],
            "secret": cfg["secret"],
            # TODO: expose SSH port — currently hardcoded to 22 (future enhancement)
        }
        ui.info(f"Connecting to {p['name']} ({p['host']}) ...")
        try:
            with ConnectHandler(**device) as conn:
                if cfg["secret"]:
                    conn.enable()
                conn.send_config_set(p["commands"])
                if cfg["save"]:
                    conn.save_config()
            ui.ok(f"{p['name']}: configuration applied.")
            results.append((p["name"], True))

        except NetmikoAuthenticationException:
            ui.error(f"{p['name']}: authentication failed "
                     f"(check username / password / enable secret).")
            results.append((p["name"], False))
        except NetmikoTimeoutException:
            ui.error(f"{p['name']}: timeout "
                     f"(check IP, reachability, and that SSH is enabled).")
            results.append((p["name"], False))
        except Exception as exc:  # noqa: BLE001 - surface anything else cleanly
            ui.error(f"{p['name']}: {exc}")
            results.append((p["name"], False))

    # --- summary ----------------------------------------------------------
    ui.section("Summary")
    for name, success in results:
        status = (f"{ui.GREEN}SUCCESS{ui.RESET}" if success
                  else f"{ui.RED}FAILED{ui.RESET}")
        print(f"  {name}: {status}")
