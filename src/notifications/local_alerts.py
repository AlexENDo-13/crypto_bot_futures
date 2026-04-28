#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Alerts v1.0
Звуковые и визуальные алерты без интернета.
Windows: winsound + toast. Linux: notify2 + paplay. Голос через pyttsx3.
"""
import logging
import platform
import threading
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LocalAlerts:
    """
    Локальные алерты — работают без интернета.

    Usage:
        alerts = LocalAlerts()
        alerts.notify("Позиция закрыта", "BTC +$12.40", sound=True)
        alerts.speak("Сделка в плюс")
    """

    def __init__(self, enable_sound: bool = True, enable_voice: bool = False,
                 enable_toast: bool = True):
        self.enable_sound = enable_sound
        self.enable_voice = enable_voice
        self.enable_toast = enable_toast
        self._system = platform.system()
        self._voice_engine = None

        if self.enable_voice:
            self._init_voice()

    def _init_voice(self):
        """Инициализация голосового движка."""
        try:
            import pyttsx3
            self._voice_engine = pyttsx3.init()
            self._voice_engine.setProperty('rate', 150)
            logger.info("Voice engine initialized")
        except ImportError:
            logger.warning("pyttsx3 not installed. Voice alerts disabled.")
            self.enable_voice = False

    def notify(self, title: str, message: str, sound: bool = True, 
               urgency: str = "normal"):
        """Показать системное уведомление."""
        if not self.enable_toast:
            return

        try:
            if self._system == "Windows":
                self._notify_windows(title, message)
            elif self._system == "Linux":
                self._notify_linux(title, message, urgency)
            elif self._system == "Darwin":
                self._notify_macos(title, message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")

        if sound and self.enable_sound:
            self._play_sound(urgency)

    def _notify_windows(self, title: str, message: str):
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            # Fallback: ctypes MessageBox
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)

    def _notify_linux(self, title: str, message: str, urgency: str):
        try:
            import subprocess
            urgency_flag = "-u critical" if urgency == "critical" else "-u normal"
            subprocess.run([
                "notify-send", urgency_flag, "-t", "5000",
                title, message
            ], check=False)
        except FileNotFoundError:
            logger.debug("notify-send not found")

    def _notify_macos(self, title: str, message: str):
        import subprocess
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], check=False)

    def _play_sound(self, urgency: str = "normal"):
        """Воспроизвести звук."""
        try:
            if self._system == "Windows":
                import winsound
                if urgency == "critical":
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                else:
                    winsound.MessageBeep(winsound.MB_OK)
            elif self._system == "Linux":
                import subprocess
                sound_file = "/usr/share/sounds/freedesktop/stereo/message.oga"
                subprocess.run(["paplay", sound_file], check=False)
        except Exception as e:
            logger.debug(f"Sound play failed: {e}")

    def speak(self, text: str):
        """Голосовое оповещение."""
        if not self.enable_voice or not self._voice_engine:
            return

        def _speak_thread():
            try:
                self._voice_engine.say(text)
                self._voice_engine.runAndWait()
            except Exception as e:
                logger.error(f"Voice error: {e}")

        thread = threading.Thread(target=_speak_thread, daemon=True)
        thread.start()

    def trade_alert(self, symbol: str, pnl: float, side: str = "closed"):
        """Готовый алерт для сделки."""
        emoji = "🟢" if pnl > 0 else "🔴"
        title = f"{emoji} {symbol} {side.upper()}"
        message = f"PnL: {pnl:+.2f} USDT"

        self.notify(title, message, sound=True, 
                   urgency="critical" if pnl < 0 else "normal")

        if self.enable_voice:
            direction = "в плюс" if pnl > 0 else "в минус"
            self.speak(f"Сделка {symbol} закрыта {direction}")

    def error_alert(self, error_message: str):
        """Алерт об ошибке."""
        self.notify("❌ Ошибка бота", error_message, sound=True, urgency="critical")
        if self.enable_voice:
            self.speak("Внимание, ошибка в работе бота")
