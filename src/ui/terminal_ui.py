#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terminal UI v1.0
TUI интерфейс на rich — лёгкая альтернатива PyQt GUI.
Подходит для слабых ноутбуков и headless-серверов.
"""
import logging
import time
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class TerminalUI:
    """
    Терминальный интерфейс бота.

    Usage:
        ui = TerminalUI(mode_switcher=mode, position_tracker=pt, database=db)
        ui.start()  # Блокирующий цикл
    """

    def __init__(self, mode_switcher=None, position_tracker=None, 
                 database=None, performance_profile=None):
        self.mode_switcher = mode_switcher
        self.position_tracker = position_tracker
        self.db = database
        self.profile = performance_profile
        self._running = False
        self._refresh_interval = 2.0
        self._commands = {
            "q": self._quit,
            "quit": self._quit,
            "p": self._pause,
            "pause": self._pause,
            "r": self._resume,
            "resume": self._resume,
            "s": self._status,
            "status": self._status,
            "pos": self._positions,
            "positions": self._positions,
            "mode": self._switch_mode,
            "help": self._help,
        }

    def start(self):
        """Запустить TUI. Блокирующий метод."""
        self._running = True

        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            from rich.layout import Layout
            from rich.live import Live
            RICH_AVAILABLE = True
        except ImportError:
            RICH_AVAILABLE = False
            logger.warning("rich not installed. Using simple terminal output.")

        if RICH_AVAILABLE:
            self._run_rich_ui()
        else:
            self._run_simple_ui()

    def _run_rich_ui(self):
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.layout import Layout
        from rich.live import Live

        console = Console()

        def generate_layout():
            layout = Layout()

            # Header
            mode = self.mode_switcher.mode_name if self.mode_switcher else "unknown"
            header = Panel(
                f"🤖 CryptoBot v12 | Mode: [bold cyan]{mode.upper()}[/] | "
                f"Time: {datetime.now().strftime('%H:%M:%S')}",
                style="bold white on blue"
            )

            # Stats
            stats = self._get_stats()
            stats_text = "\n".join([
                f"📊 PnL Today: {stats.get('pnl_today', 0):+.2f} USDT",
                f"📈 Open Pos: {stats.get('open_positions', 0)}",
                f"💾 RAM: {stats.get('ram_mb', 0):.0f}MB",
                f"🔋 {stats.get('battery', 'N/A')}",
            ])
            stats_panel = Panel(stats_text, title="[bold green]Stats[/]")

            # Positions table
            pos_table = self._get_positions_table()

            # Commands
            commands = Panel(
                "[yellow]q[/]uit | [yellow]p[/]ause | [yellow]r[/]esume | "
                "[yellow]s[/]tatus | [yellow]pos[/]itions | [yellow]mode[/] <name> | [yellow]help[/]",
                title="[bold yellow]Commands[/]"
            )

            layout.split_column(
                Layout(header, size=3),
                Layout(name="main"),
                Layout(commands, size=3)
            )
            layout["main"].split_row(
                Layout(stats_panel, size=30),
                Layout(pos_table)
            )
            return layout

        with Live(generate_layout(), refresh_per_second=2, screen=True) as live:
            # Input thread
            def input_loop():
                while self._running:
                    try:
                        cmd = input().strip().lower()
                        self._handle_command(cmd)
                    except EOFError:
                        break

            input_thread = threading.Thread(target=input_loop, daemon=True)
            input_thread.start()

            while self._running:
                live.update(generate_layout())
                time.sleep(self._refresh_interval)

    def _run_simple_ui(self):
        """Простой вывод без rich."""
        print("=" * 60)
        print("  CryptoBot Terminal UI (simple mode)")
        print("=" * 60)
        print("Commands: quit | pause | resume | status | positions | help")
        print("-" * 60)

        while self._running:
            self._print_status()
            try:
                cmd = input("
> ").strip().lower()
                self._handle_command(cmd)
            except EOFError:
                break
            time.sleep(self._refresh_interval)

    def _print_status(self):
        stats = self._get_stats()
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
              f"Mode: {stats.get('mode', '?')} | "
              f"PnL: {stats.get('pnl_today', 0):+.2f} | "
              f"Pos: {stats.get('open_positions', 0)} | "
              f"RAM: {stats.get('ram_mb', 0):.0f}MB")

    def _get_stats(self) -> Dict[str, Any]:
        stats = {"mode": "?", "pnl_today": 0, "open_positions": 0, 
                 "ram_mb": 0, "battery": "N/A"}

        if self.mode_switcher:
            stats["mode"] = self.mode_switcher.mode_name

        if self.db:
            try:
                trade_stats = self.db.get_trade_stats(days=1)
                stats["pnl_today"] = trade_stats.get("total_pnl", 0)
            except Exception:
                pass

        if self.position_tracker:
            try:
                stats["open_positions"] = len(self.position_tracker.get_open_positions())
            except Exception:
                pass

        if self.profile:
            try:
                profile_stats = self.profile.get_stats()
                stats["ram_mb"] = profile_stats.get("process_memory_mb", 0)
            except Exception:
                pass

        return stats

    def _get_positions_table(self):
        from rich.table import Table
        table = Table(title="Open Positions")
        table.add_column("Symbol", style="cyan")
        table.add_column("Side", style="green")
        table.add_column("Entry", style="yellow")
        table.add_column("Current", style="yellow")
        table.add_column("PnL%", style="bold")

        if self.position_tracker:
            try:
                positions = self.position_tracker.get_open_positions()
                for pos in positions:
                    pnl_pct = pos.get("pnl_percent", 0)
                    color = "green" if pnl_pct > 0 else "red"
                    table.add_row(
                        pos.get("symbol", "?"),
                        pos.get("side", "?"),
                        str(pos.get("entry_price", 0)),
                        str(pos.get("current_price", 0)),
                        f"[{color}]{pnl_pct:+.2f}%[/{color}]"
                    )
            except Exception:
                table.add_row("—", "—", "—", "—", "—")

        return table

    def _handle_command(self, cmd: str):
        parts = cmd.split()
        if not parts:
            return

        command = parts[0]
        args = parts[1:]

        handler = self._commands.get(command)
        if handler:
            handler(args)
        else:
            print(f"Unknown command: {command}. Type 'help' for list.")

    def _quit(self, args=None):
        print("👋 Shutting down...")
        self._running = False

    def _pause(self, args=None):
        if self.mode_switcher:
            from src.core.mode_switcher import BotMode
            self.mode_switcher.switch_to(BotMode.PAUSED, reason="terminal_command")
        print("⏸️ Bot paused")

    def _resume(self, args=None):
        if self.mode_switcher:
            from src.core.mode_switcher import BotMode
            self.mode_switcher.switch_to(BotMode.TREND, reason="terminal_command")
        print("▶️ Bot resumed")

    def _status(self, args=None):
        stats = self._get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")

    def _positions(self, args=None):
        if self.position_tracker:
            try:
                positions = self.position_tracker.get_open_positions()
                for pos in positions:
                    print(f"  {pos}")
            except Exception as e:
                print(f"Error: {e}")

    def _switch_mode(self, args):
        if not args:
            print("Usage: mode <trend|grid|dca|paused|light>")
            return
        if self.mode_switcher:
            from src.core.mode_switcher import BotMode
            try:
                mode = BotMode(args[0])
                self.mode_switcher.switch_to(mode, reason="terminal_command")
                print(f"✅ Mode switched to {args[0]}")
            except ValueError:
                print("❌ Unknown mode")

    def _help(self, args=None):
        print("Commands:")
        print("  q/quit     — Exit bot")
        print("  p/pause    — Pause trading")
        print("  r/resume   — Resume trading")
        print("  s/status   — Show status")
        print("  pos        — Show positions")
        print("  mode <name>— Switch mode")
        print("  help       — This message")

    def stop(self):
        self._running = False
