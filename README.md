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
| 1 | First-Touch Config (Simulation) | ready |
| 2 | ConfigForge — Bulk Config Push (SSH + Simulation) | ready |
| 3 | NetDoctor — AI Troubleshooter (SSH + Simulation) | ready |
| 4 | NetAudit — Compliance Checker (SSH + Simulation) | ready |
| 5 | NetBackup — Config Backup Manager (SSH + Simulation) | ready |

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

## First-Touch Config
Bootstraps a factory-default Cisco device from zero to SSH-ready in one pass. No existing credentials needed — this is the very first thing you run on a new device.

Configures in order:
- Hostname and `no ip domain-lookup`
- `service password-encryption`, `enable secret`, `banner motd`
- Local user (privilege 15) for SSH login
- `ip domain-name`, `crypto key generate rsa modulus 2048`, `ip ssh version 2`
- `line vty 0 15`: `login local`, `transport input ssh`
- `line console 0`: password, login, exec-timeout
- Management IP: SVI + default-gateway (switch) or physical interface (router)
- `write memory`

Simulation mode exports a paste-ready IOS block to `output/first_touch_<hostname>.txt` — works with Packet Tracer. Console cable mode (Coming Soon) will push directly via pyserial over USB-to-RJ45.

## NetAudit

Checks a device's running configuration against a user-defined compliance baseline stored in `baseline.json`. Connects over SSH (read-only) or reads from a saved running-config file in Simulation mode.

**Default baseline (auto-generated on first run):**
10 CCNA security hardening rules covering enable secret, service password-encryption, SSH v2, HTTP server disabled, banner motd, console exec-timeout, VTY SSH-only, VTY login local, no ip domain-lookup, and no telnet.

**Customizing the baseline:**
Edit `baseline.json` to add, remove, or change rules. Each rule specifies an id, description, check type (`must_contain` / `must_not_contain` / `must_match_regex`), value, severity (critical/high/medium/low), and the exact IOS fix command. The baseline is version-controlled alongside your code so compliance requirements are tracked over time.

**Output:** `output/<hostname>_audit.txt` with score, failed rules with fix commands, and passed rules.

## NetBackup

Connects to one device or a series over SSH and saves each device's running configuration to a timestamped backup file. Strictly read-only.

Backups are saved to:
```
backups/<hostname>/<hostname>_<YYYY-MM-DD_HH-MM>.txt
```

Each backup file includes a 5-line header with device name, IP, timestamp, and NetBackup attribution, followed by the raw running-config output. The `backups/` folder is excluded from git (`.gitignore`) since running configs contain sensitive network topology information.

Simulation mode generates a template file you can fill with real `show running-config` output for testing backup workflows without a live device.

## Lab / testing (GNS3)

Host-side Python **cannot** reach Cisco Packet Tracer devices (PT doesn't bridge
to the host network stack), so ConfigForge is tested against **GNS3**:

1. Add an IOSv / IOSvL2 device to your topology.
2. Give it a management IP and enable SSH:
   `hostname`, `ip domain-name`, `crypto key generate rsa`,
   a local `username … privilege 15 secret …`, and `transport input ssh` on the vty lines.
3. Bridge the topology to your host with a **Cloud** or **NAT** node so your laptop can reach the management IP.

## Roadmap

- First-Touch Config: console-cable mode (needs USB-to-RJ45 cable + pyserial)
- ConfigForge: console-cable connection method
- ConfigForge: configurable SSH port (currently port 22)
- NetDoctor: console-cable connection method
- NetDoctor: TextFSM/Genie structured parsing
- NetScan — subnet discovery tool (planned)

## Author

**A. Wassim**
GitHub: https://github.com/wassimsmt
LinkedIn: https://www.linkedin.com/in/wassim-abelghouch/

## License

MIT — see [LICENSE](LICENSE).
