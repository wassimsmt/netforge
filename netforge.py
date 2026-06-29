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
from rich.table import Table
from ui import console


def main_menu():
    table = Table(show_header=True, header_style="bold cyan",
                  border_style="blue", show_lines=False)
    table.add_column("#",      style="bold green", width=4)
    table.add_column("Module", style="white",      min_width=35)
    table.add_column("Status", style="white",      width=14)

    table.add_row("1", "First-Touch Config",             "[yellow]Coming Soon[/yellow]")
    table.add_row("2", "ConfigForge — Bulk Config Push", "[green]● ready[/green]")
    table.add_row("3", "NetDoctor  — AI Troubleshooter", "[green]● ready[/green]")
    table.add_row("0", "Exit", "")

    console.print(table)
    console.print()


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
