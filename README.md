# NetForge — Network Automation Toolkit

`v1.0` · built by **A. Wassim**

A small, interactive Python toolkit for network administrators. Run one launcher,
pick a module, answer a few prompts, review a preview, and apply.

```
 ███╗   ██╗███████╗████████╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗
 ████╗  ██║██╔════╝╚══██╔══╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
 ██╔██╗ ██║█████╗     ██║   █████╗  ██║   ██║██████╔╝██║  ███╗█████╗
 ██║╚██╗██║██╔══╝     ██║   ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
 ██║ ╚████║███████╗   ██║   ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
 ╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
```

## Modules

| # | Module | Status |
|---|--------|--------|
| 1 | First-Touch Config | Coming Soon |
| 2 | **ConfigForge** — Bulk Config Push (SSH) | ready |
| 3 | NetDoctor — AI Troubleshooter | Coming Soon |

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python netforge.py
```

## ConfigForge

Pushes a full CCNA-style configuration to one device or a named series
(`SW1-FLOOR1 … SWn-FLOOR1`) over **SSH**, or use **Simulation / Dry-run** mode
to export paste-ready IOS config blocks to `output/<hostname>.txt` — no device needed.

Select a **device type** at startup (Switch / Router / Both) and only the sections
that apply to that device are offered.

**15 configuration sections (v2.0):**

| Section | Scope |
|---------|-------|
| A — Device Baseline | All |
| B — VLANs | Switch / Both |
| C — Access Ports | Switch / Both |
| D — Trunking | Switch / Both |
| E — STP | Switch / Both |
| F — EtherChannel | Switch / Both |
| G — CDP / LLDP | All |
| H — Router Interfaces & IP | Router / Both |
| I — Static Routing | Router / Both |
| J — OSPF | Router / Both |
| K — DHCP Server | Router / Both |
| L — NAT | Router / Both |
| M — ACLs | All |
| N — QoS | All |
| O — Security Hardening | All |

Passwords are read with `getpass` (never echoed) and masked in the on-screen preview.
Simulation mode writes plaintext passwords to file — `output/` is in `.gitignore`.
Nothing is sent to a device until you type **yes** at the confirmation step.

## Lab / testing (GNS3)

Host-side Python **cannot** reach Cisco Packet Tracer devices (PT doesn't bridge
to the host network stack), so ConfigForge is tested against **GNS3**:

1. Add an IOSv / IOSvL2 device to your topology.
2. Give it a management IP and enable SSH:
   `hostname`, `ip domain-name`, `crypto key generate rsa`,
   a local `username … privilege 15 secret …`, and `transport input ssh` on the vty lines.
3. Bridge the topology to your host with a **Cloud** or **NAT** node so your laptop can reach the management IP.

## Roadmap

- First-Touch Config (console/serial bootstrap)
- ConfigForge: console-cable connection method
- NetDoctor: read-only `show`-command collection + parsing + AI-assisted report

## Author

**A. Wassim**
GitHub: https://github.com/wassimsmt
LinkedIn: https://www.linkedin.com/in/wassim-abelghouch/

## License

MIT — see [LICENSE](LICENSE).
