#!/usr/bin/env python3
"""
NetForge — Network Automation Toolkit (launcher)

Run me:  python netforge.py

  [1] First-Touch Config        (Coming Soon)
  [2] ConfigForge — Bulk Config Push     ready
  [3] NetDoctor  — AI Troubleshooter     (Coming Soon)
  [0] Exit

built by A. Wassim  ·  github.com/wassimsmt  ·  MIT License
"""
import sys

import ui
import configforge


def main_menu():
    print(f"{ui.WHITE}{ui.BRIGHT}  Main Menu{ui.RESET}")
    print(f"  {ui.GREEN}[1]{ui.RESET} First-Touch Config              "
          f"{ui.YELLOW}(Coming Soon){ui.RESET}")
    print(f"  {ui.GREEN}[2]{ui.RESET} ConfigForge — Bulk Config Push  "
          f"{ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[3]{ui.RESET} NetDoctor  — AI Troubleshooter   "
          f"{ui.GREEN}ready{ui.RESET}")
    print(f"  {ui.GREEN}[0]{ui.RESET} Exit")
    print()


def main():
    ui.banner()
    while True:
        main_menu()
        choice = ui.ask("Select an option >")

        if choice == "1":
            ui.coming_soon("First-Touch Config")
        elif choice == "2":
            configforge.run()
        elif choice == "3":
            import netdoctor
            netdoctor.run()
        elif choice == "0":
            ui.info("Goodbye.")
            sys.exit(0)
        else:
            ui.warn("Invalid choice — please pick 0-3.")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        ui.warn("Interrupted. Exiting.")
        sys.exit(0)
