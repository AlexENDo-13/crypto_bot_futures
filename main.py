#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crypto Trading Bot v3.1 — BingX Futures. Исправлено: стабильный запуск, защита от GC, интеграция логгера."""
import sys, os, signal, argparse, traceback, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from src.config.settings import Settings
from src.ui.main_window import MainWindow, apply_dark_theme
from src.utils.self_healing import SelfHealingMonitor
from src.core.logger import BotLogger

def signal_handler(sig, frame):
    print("\n🛑 Сигнал прерывания. Завершение...")
    app = QApplication.instance()
    if app: app.quit()

def main():
    parser = argparse.ArgumentParser(description="Crypto Trading Bot v3.1")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--config", type=str, default="config/bot_config.json")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    try:
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, "SIGTERM"): signal.signal(signal.SIGTERM, signal_handler)
    except Exception: pass
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
    app.setApplicationName("Crypto Trading Bot v3.1")
    app.setApplicationVersion("3.1.0")
    apply_dark_theme(app)
    logger = BotLogger(name="Bot", level="INFO", log_dir="logs")
    logger.info("🚀 Инициализация бота v3.1...")
    try:
        settings = Settings(config_path=args.config)
        if args.demo:
            settings.set("demo_mode", True)
            logger.info("Демо-режим принудительно включён")
        healing = SelfHealingMonitor()
        healing.start()
        window = MainWindow(settings, logger=logger, healing_monitor=healing)
        window.show()
        logger.info("✅ GUI инициализирован, ожидание запуска...")
        exit_code = app.exec_()
        healing.stop()
        logger.info(f"👋 Бот завершил работу (код: {exit_code})")
        sys.exit(exit_code)
    except Exception as e:
        err_msg = f"Критическая ошибка: {e}\n{traceback.format_exc()}"
        print(err_msg)
        try: logger.critical(err_msg)
        except: pass
        QMessageBox.critical(None, "Критическая ошибка", str(e))
        sys.exit(1)

if __name__ == "__main__": main()
