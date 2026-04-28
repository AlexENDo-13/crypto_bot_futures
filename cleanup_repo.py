#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CryptoBot Repository Cleaner v1.1 (fixed)
Удаляет дублирующие, мусорные и временные файлы.
Исправления: --dry-run, --yes, защита .env, чистка пустых папок.
"""
import os
import sys
import shutil
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

TO_DELETE = {
    "duplicates": [
        "src/exchange/data_fetcher.py", "src/trading/data_fetcher.py",
        "src/exchange/market_scanner.py", "src/trading/market_scanner.py",
        "src/exchange/trade_executor.py", "src/trading/trade_executor.py",
        "src/trading/risk_manager.py", "src/risk/risk_manager.py",
        "src/trading/position_manager.py", "src/core/settings.py",
        "src/core/state_manager.py", "src/state/state_manager.py",
        "src/utils/state_manager.py", "src/utils/logger.py",
        "src/utils/api_client.py", "src/ai/ml_engine.py",
        "src/utils/ai_exporter.py",
        "src/notifications/telegram_notifier.py", "src/notifications/discord_notifier.py",
    ],
    "junk_files": [
        "README.txt", "README_v8.0.txt", "README_v9.0.txt", "gitignore", "FIXES_README.txt",
        "cleanup_and_fix.py", "emergency_fix.py", "safe_patcher.py", "git_helper_v2.py",
        "bingx_diagnostic.py", "standalone_exporter.py", "test_bingx.py", "tester.py", "fix.patch",
        "FULL_DUMP_20260423_103932.json", "FULL_DUMP_20260423_104005.json",
        "diagnostic_report.json", "bingx_diagnostic_report.json",
        "crypto_bot_futures_fixed.zip", "logs/trading_bot.log",
        "data/trades.db", "data/history/trades.db", "data/proxies.txt", "data/security/salt.bin",
    ],
    "patterns": ["*.bak", "*.bak.*", "*.pyc", "*.pyo", "*.orig", "*.rej"],
    "folders": [
        "src/core/engine/.patches_backup", "src/core/executor/.patches_backup",
        "src/core/exit/.patches_backup", "src/core/risk/.patches_backup",
        "src/core/trading/.patches_backup", "src/config/.patches_backup",
        "data/backups", "data/logs", "data/history", "data/security", "logs",
        "src/data/ai_exports", "src/config/__pycache__",
        "src/core/__pycache__", "src/ui/__pycache__",
    ],
}

PROTECTED = {
    "main.py", "requirements.txt", "setup.py", ".gitignore", "README.md", "QUICK_START.md",
    "config/bot_config.json", "config/settings.json",
    "src/__init__.py", "src/exchange/__init__.py", "src/exchange/api_client.py",
    "src/exchange/websocket_client.py", "src/config/__init__.py",
    "src/config/settings.py", "src/config/constants.py", "src/core/__init__.py",
    "src/core/logger.py", "src/core/state.py", "src/core/events.py",
    "src/core/monitor.py", "src/core/notifications.py", "src/core/security.py",
    "src/core/autopilot.py", "src/core/engine/__init__.py",
    "src/core/engine/trading_engine.py", "src/core/executor/__init__.py",
    "src/core/executor/trade_executor.py", "src/core/exit/__init__.py",
    "src/core/exit/exit_manager.py", "src/core/market/__init__.py",
    "src/core/market/data_fetcher.py", "src/core/market/indicators.py",
    "src/core/market/trap_detector.py", "src/core/risk/__init__.py",
    "src/core/risk/risk_manager.py", "src/core/risk/risk_controller.py",
    "src/core/risk/adaptive_risk.py", "src/core/scanner/__init__.py",
    "src/core/scanner/market_scanner.py", "src/core/signals/__init__.py",
    "src/core/signals/candle_patterns.py", "src/core/signals/signal_evaluator.py",
    "src/core/trading/__init__.py", "src/core/trading/order_manager.py",
    "src/core/trading/position.py", "src/ai/__init__.py", "src/ai/ai_exporter.py",
    "src/analytics/__init__.py", "src/backtest/__init__.py", "src/backtest/backtester.py",
    "src/data/__init__.py", "src/data/backtest/__init__.py",
    "src/data/history/__init__.py", "src/data/models/__init__.py",
    "src/intelligence/__init__.py", "src/intelligence/self_healing.py",
    "src/intelligence/strategy_engine.py", "src/intelligence/genetic/__init__.py",
    "src/intelligence/neural/__init__.py", "src/ml/__init__.py",
    "src/ml/feature_engineering.py", "src/ml/ml_engine.py",
    "src/ml/model_trainer.py", "src/ml/predictor.py",
    "src/notifications/__init__.py", "src/notifications/telegram.py",
    "src/notifications/discord.py", "src/plugins/__init__.py",
    "src/plugins/strategy_base.py", "src/plugins/ema_cross.py",
    "src/plugins/macd_momentum.py", "src/plugins/rsi_divergence.py",
    "src/plugins/bollinger_squeeze.py", "src/plugins/support_resistance.py",
    "src/plugins/volume_breakout.py", "src/security/__init__.py",
    "src/security/key_encryption.py", "src/state/__init__.py",
    "src/strategies/__init__.py", "src/strategies/base_strategy.py",
    "src/strategies/strategies.py", "src/trading/__init__.py",
    "src/ui/__init__.py", "src/ui/main_window.py", "src/ui/system_tray.py",
    "src/ui/styles.qss", "src/ui/pages/__init__.py", "src/ui/pages/config.py",
    "src/ui/pages/dashboard.py", "src/ui/pages/logs.py", "src/ui/pages/positions.py",
    "src/ui/pages/system_monitor.py", "src/ui/pages/trades_history.py",
    "src/ui/widgets/__init__.py", "src/ui/widgets/log_viewer.py",
    "src/ui/widgets/pie_chart.py", "src/ui/widgets/realtime_chart.py",
    "src/utils/__init__.py", "src/utils/async_bridge.py", "src/utils/auto_recovery.py",
    "src/utils/cache_manager.py", "src/utils/performance_metrics.py",
    "src/utils/profiler.py", "src/utils/self_healing.py", "src/utils/sqlite_history.py",
    "src/web/__init__.py", "src/web/app.py", "src/web/web_server.py",
}

PROTECTED_PATTERNS = [".env", ".env.*", "*.key", "*.pem", "secrets.json", "credentials.json"]

def get_project_root() -> Path:
    script_dir = Path(__file__).parent.resolve()
    if (script_dir / "main.py").exists():
        return script_dir
    for parent in script_dir.parents:
        if (parent / "main.py").exists():
            return parent
    return script_dir

def is_protected(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    if rel in PROTECTED: return True
    if ".git" in path.parts: return True
    if "config" in path.parts and path.suffix == ".json": return True
    for pat in PROTECTED_PATTERNS:
        if path.match(pat): return True
    if path == root: return True
    return False

def collect_targets(root: Path):
    files_to_delete, folders_to_delete, protected_skipped = [], [], []
    for category in ["duplicates", "junk_files"]:
        for rel_path in TO_DELETE.get(category, []):
            full_path = root / rel_path
            if full_path.exists():
                (protected_skipped if is_protected(full_path, root) else files_to_delete).append(full_path)
    for pattern in TO_DELETE.get("patterns", []):
        for found in list(root.rglob(pattern)):
            if is_protected(found, root): protected_skipped.append(found)
            else: files_to_delete.append(found)
    for rel_folder in TO_DELETE.get("folders", []):
        full_path = root / rel_folder
        if full_path.exists() and full_path.is_dir():
            (protected_skipped if is_protected(full_path, root) else folders_to_delete).append(full_path)
    seen = set()
    unique_files = [p for p in files_to_delete if not (p in seen or seen.add(p))]
    seen = set()
    unique_folders = [p for p in folders_to_delete if not (p in seen or seen.add(p))]
    return unique_files, unique_folders, protected_skipped

def create_backup(root, files, folders):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / "backups" / f"cleanup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            rel = f.relative_to(root)
            dest = backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        except Exception as e: print(f"  ⚠️ Backup error for {f}: {e}")
    for folder in folders:
        try:
            rel = folder.relative_to(root)
            dest = backup_dir / rel
            if folder.exists(): shutil.copytree(folder, dest, dirs_exist_ok=True)
        except Exception as e: print(f"  ⚠️ Backup error for {folder}: {e}")
    manifest = {"timestamp": timestamp, "files": [str(f.relative_to(root)) for f in files],
                "folders": [str(f.relative_to(root)) for f in folders]}
    with open(backup_dir / "_manifest.json", "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2, ensure_ascii=False)
    return backup_dir

def format_size(size_bytes):
    if size_bytes < 0: return "???"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024: return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def calculate_size(paths):
    total = 0
    for p in paths:
        if not p.exists(): continue
        if p.is_file(): total += p.stat().st_size
        elif p.is_dir():
            for item in p.rglob("*"):
                if item.is_file(): total += item.stat().st_size
    return total

def remove_empty_dirs(root, dry_run=False):
    removed = []
    for dirpath, dirnames, filenames in os.walk(str(root), topdown=False):
        dpath = Path(dirpath)
        if ".git" in dpath.parts or dpath == root: continue
        if not any(dpath.iterdir()):
            if not dry_run:
                try: dpath.rmdir(); removed.append(dpath)
                except Exception: pass
            else: removed.append(dpath)
    return removed

def main():
    parser = argparse.ArgumentParser(description="CryptoBot Repository Cleaner v1.1")
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    args = parser.parse_args()
    print("=" * 70); print("  CryptoBot Repository Cleaner v1.1"); print("=" * 70)
    root = get_project_root()
    print(f"\n📁 Project root: {root}\n")
    files, folders, protected = collect_targets(root)
    if not files and not folders:
        print("✅ Nothing to clean.")
        if not args.dry_run:
            empty = remove_empty_dirs(root)
            if empty: print(f"\n🧹 Removed {len(empty)} empty directories.")
        return 0
    print(f"🔍 Found {len(files)} files and {len(folders)} folders to delete:\n")
    if files:
        print("  📄 FILES TO DELETE:")
        total_file_size = 0
        for f in sorted(files):
            size = f.stat().st_size if f.exists() else 0
            total_file_size += size
            print(f"     - {f.relative_to(root)} ({format_size(size)})")
        print(f"     Total: {format_size(total_file_size)}\n")
    if folders:
        print("  📁 FOLDERS TO DELETE:")
        total_folder_size = 0
        for folder in sorted(folders):
            size = calculate_size([folder])
            total_folder_size += size
            print(f"     - {folder.relative_to(root)} ({format_size(size)})")
        print(f"     Total: {format_size(total_folder_size)}\n")
    if protected:
        print(f"  🛡️ PROTECTED (skipped): {len(protected)} items")
        for p in protected[:10]: print(f"     ~ {p.relative_to(root)}")
        if len(protected) > 10: print(f"     ... and {len(protected) - 10} more")
        print()
    total_size = calculate_size(files + folders)
    print(f"  💾 Total space to free: {format_size(total_size)}\n")
    if args.dry_run: print("🏁 DRY RUN — nothing deleted."); return 0
    print("⚠️  WARNING: This will DELETE files permanently (after backup).")
    print("    Backup: backups/cleanup_YYYYMMDD_HHMMSS/\n")
    if not args.yes:
        try: answer = input("  Proceed? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt): print("\n❌ Cancelled."); return 1
        if answer not in ("y", "yes"): print("❌ Cancelled by user."); return 0
    print("\n💾 Creating backup...")
    backup_path = create_backup(root, files, folders)
    print(f"   Backup: {backup_path}\n")
    deleted_files, deleted_folders, errors = 0, 0, []
    print("🗑️  Deleting files...")
    for f in files:
        try: rel = f.relative_to(root); f.unlink(); print(f"   ✓ {rel}"); deleted_files += 1
        except Exception as e: print(f"   ✗ {rel} — {e}"); errors.append((str(rel), str(e)))
    print("\n🗑️  Deleting folders...")
    for folder in folders:
        try: rel = folder.relative_to(root); shutil.rmtree(folder); print(f"   ✓ {rel}"); deleted_folders += 1
        except Exception as e: print(f"   ✗ {rel} — {e}"); errors.append((str(rel), str(e)))
    print("\n🧹 Cleaning empty directories...")
    empty_removed = remove_empty_dirs(root)
    if empty_removed: print(f"   Removed {len(empty_removed)} empty dirs")
    print("\n" + "=" * 70); print("  CLEANUP COMPLETE"); print("=" * 70)
    print(f"  Files deleted:    {deleted_files}/{len(files)}")
    print(f"  Folders deleted:  {deleted_folders}/{len(folders)}")
    print(f"  Empty dirs:       {len(empty_removed)}")
    print(f"  Space freed:      {format_size(total_size)}")
    print(f"  Backup:           {backup_path}")
    if errors: print(f"  Errors:           {len(errors)}")
    print("=" * 70)
    return 0

if __name__ == "__main__": sys.exit(main())
