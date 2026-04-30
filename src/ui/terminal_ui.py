#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terminal UI v1.1 — Non-blocking, works alongside GUI or standalone.
"""
import logging
import time
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class TerminalUI:
    def __init__(self, mode_switcher=None, position_tracker=None,
                 database=None, performance_profile=None):
        self.mode_switcher = mode_switcher
        self.position_tracker = position_tracker
        self.db = database
        self.profile = performance_profile
        self._running = False
        self._refresh_interval = 5.0
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
        """Start TUI in background thread."""
        self._running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        logger.info("TerminalUI started in background thread")

    def _run(self):
        print("=" * 60)
        print(" CryptoBot Terminal UI (v1.1)")
        print("=" * 60)
        print("Commands: quit | pause | resume | status | positions | help")
        print("-" * 60)

        while self._running:
            self._print_status()
            try:
                cmd = input("> ").strip().lower()
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
        print("Shutting down...")
        self._running = False

    def _pause(self, args=None):
        if self.mode_switcher:
            from src.core.mode_switcher import BotMode
            self.mode_switcher.switch_to(BotMode.PAUSED, reason="terminal_command")
            print("Bot paused")

    def _resume(self, args=None):
        if self.mode_switcher:
            from src.core.mode_switcher import BotMode
            self.mode_switcher.switch_to(BotMode.TREND, reason="terminal_command")
            print("Bot resumed")

    def _status(self, args=None):
        stats = self._get_stats()
        for k, v in stats.items():
            print(f" {k}: {v}")

    def _positions(self, args=None):
        if self.position_tracker:
            try:
                positions = self.position_tracker.get_open_positions()
                for pos in positions:
                    print(f" {pos}")
            except Exception as e:
                print(f"Error: {e}")

    def _switch_mode(self, args):
        if not args:
            print("Usage: mode <trend|grid|dca|paused|emergency>")
            return
        if self.mode_switcher:
            from src.core.mode_switcher import BotMode
            try:
                mode = BotMode(args[0])
                self.mode_switcher.switch_to(mode, reason="terminal_command")
                print(f"Mode switched to {args[0]}")
            except ValueError:
                print("Unknown mode")

    def _help(self, args=None):
        print("Commands:")
        print(" q/quit — Exit bot")
        print(" p/pause — Pause trading")
        print(" r/resume — Resume trading")
        print(" s/status — Show status")
        print(" pos — Show positions")
        print(" mode — Switch mode")
        print(" help — This message")

    def stop(self):
        self._running = False
