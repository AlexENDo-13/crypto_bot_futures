#!/usr/bin/env python3
import subprocess, sys
def install():
    reqs = ["PyQt5>=5.15.0","aiohttp>=3.8.0","pandas>=1.5.0","numpy>=1.23.0","psutil>=5.9.0","requests>=2.28.0","python-telegram-bot>=20.0","scikit-learn>=1.2.0","ta>=0.10.0","matplotlib>=3.6.0","schedule>=1.2.0","cryptography>=40.0.0"]
    print("📦 Установка...")
    for r in reqs:
        print(f"  → {r}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", r])
    print("✅ Готово! Запустите: python main.py")
if __name__ == "__main__": install()
