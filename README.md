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
| 2 | ConfigForge — Bulk Config Push (SSH + Simulation) | ready |
| 3 | NetDoctor — AI Troubleshooter (SSH + Simulation) | ready |

## Install

```bash
pip install -r requirements.txt
```

Dependencies: `netmiko>=4.0`, `rich>=13.0`, `pyfiglet>=1.0`, `google-genai>=1.0`

## Terminal UI
NetForge uses [Rich](https://github.com/Textualize/rich) for colored tables, panels, and section headers, and [pyfiglet](https://github.com/pwaller/pyfiglet) for the ASCII banner. Both render correctly on Windows Terminal, macOS Terminal, and Linux without any extra configuration.

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

## NetDoctor

Connects to one device or a series over SSH (read-only — never modifies config),
or reads from saved show output files in Simulation mode. Runs a curated set of
show commands, parses the output deterministically, and sends structured findings
to the Gemini 2.5 Flash API to produce a plain-language diagnostic report saved
to `output/<hostname>_report.txt`.

**Requires a free Gemini API key** (no credit card needed):
1. Go to aistudio.google.com → Get API key → Create API key
2. Set it before running:
   ```
   Windows PowerShell : $env:GEMINI_API_KEY="your-key-here"
   Permanent          : setx GEMINI_API_KEY "your-key-here"
   ```

**What it checks (deterministic parser):**

| Check | Scope |
|-------|-------|
| Interface up/down, up/up, err-disabled | Both |
| Input errors and CRC counters | Both |
| OSPF neighbor states | Router |
| Routing table / missing default route | Router |
| STP blocked ports | Switch |
| Port security violations | Switch |
| EtherChannel suspended members | Switch |
| DHCP conflicts | Router |

**Simulation mode:** create `sim_input/<hostname>/` folder automatically on first
run, paste show output into the generated `.txt` files, re-run for a full AI report —
no device needed.

NetDoctor is strictly read-only. It will never send a `configure terminal` command
to any device.

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
- ConfigForge: configurable SSH port (currently hardcoded to 22)
- NetDoctor: console-cable connection method
- NetDoctor: TextFSM/Genie structured parsing (richer analysis)

## Author

**A. Wassim**
GitHub: https://github.com/wassimsmt
LinkedIn: https://www.linkedin.com/in/wassim-abelghouch/

## License

MIT — see [LICENSE](LICENSE).
