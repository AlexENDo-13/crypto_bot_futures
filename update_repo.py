#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CryptoBot GitHub Updater v2.3 — fixed git status parser + stability."""
import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

def run(cmd, cwd=None, check=False):
    try:
        result = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            print(f"❌ Command failed: {' '.join(cmd)}"); print(f"   stderr: {result.stderr}"); sys.exit(1)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except FileNotFoundError as e: print(f"❌ Command not found: {cmd[0]} — {e}"); sys.exit(1)

def check_git_installed():
    if not shutil.which("git"): print("❌ Git не найден в PATH."); sys.exit(1)

def get_project_root():
    script_dir = Path(__file__).parent.resolve()
    if (script_dir / ".git").exists(): return script_dir
    for parent in script_dir.parents:
        if (parent / ".git").exists(): return parent
    if (script_dir / "main.py").exists(): return script_dir
    for parent in script_dir.parents:
        if (parent / "main.py").exists(): return parent
    return script_dir

def ensure_git_repo(root): return (root / ".git").exists()

def get_git_remote(root):
    stdout, _, code = run(["git", "remote", "get-url", "origin"], cwd=root)
    return stdout if code == 0 else ""

def get_branch(root):
    stdout, _, _ = run(["git", "branch", "--show-current"], cwd=root)
    return stdout or "main"

def git_status(root):
    stdout, _, _ = run(["git", "status", "--short"], cwd=root)
    modified, untracked, deleted, staged = [], [], [], []
    for line in stdout.splitlines():
        if not line.strip() or len(line) < 4: continue
        x, y = line[0], line[1]
        file_path = line[3:].strip()
        if x == '?' and y == '?': untracked.append(file_path); continue
        if x != ' ' and x != '?': staged.append(file_path)
        if x == 'M' or y == 'M': modified.append(file_path)
        elif x == 'D' or y == 'D': deleted.append(file_path)
        elif x == 'A':
            if file_path not in modified: modified.append(file_path)
    return {"modified": modified, "untracked": untracked, "deleted": deleted,
            "staged": staged, "has_changes": bool(stdout.strip())}

def show_status(root):
    print("\n📊 Git Status:"); print("-" * 50)
    stdout_f, stderr_f, code_f = run(["git", "fetch", "--quiet"], cwd=root)
    if code_f != 0: print(f"   ⚠️ Fetch warning: {stderr_f}")
    stdout, _, _ = run(["git", "status", "-sb"], cwd=root)
    print(stdout or "   Репозиторий чист.")
    print(f"\n   🌿 Ветка: {get_branch(root)}")
    print(f"   🌐 Remote: {get_git_remote(root) or 'не настроен'}")
    print("-" * 50)

def add_files(root, files=None):
    if files:
        for f in files:
            full = root / f
            if full.exists(): run(["git", "add", f], cwd=root, check=True); print(f"   ➕ Added: {f}")
            else: print(f"   ⚠️  Not found: {f}")
    else: run(["git", "add", "-A"], cwd=root, check=True); print("   ➕ Added all changes")

def commit_changes(root, message=None):
    if not message: message = f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    stdout, stderr, code = run(["git", "commit", "-m", message], cwd=root)
    if code == 0:
        h, _, _ = run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
        print(f"   ✅ Committed: [{h}] {message}"); return True
    elif "nothing to commit" in (stderr + stdout).lower(): print("   ℹ️  Nothing to commit"); return False
    else: print(f"   ❌ Commit failed: {stderr}"); return False

def push_changes(root, force=False, branch=None, dry_run=False):
    if not branch: branch = get_branch(root)
    if branch == "HEAD" or not branch: print("   ❌ Detached HEAD!"); return False
    cmd = ["git", "push", "origin", branch]
    if force: cmd.insert(2, "--force")
    if dry_run: cmd.insert(2, "--dry-run"); print(f"\n🚀 DRY-RUN push to origin/{branch}...")
    elif force: print(f"\n🚀 Force-pushing to origin/{branch}...")
    else: print(f"\n🚀 Pushing to origin/{branch}...")
    stdout, stderr, code = run(cmd, cwd=root)
    if code == 0: print(f"   ✅ {'Dry-run OK' if dry_run else 'Push successful!'}"); return True
    else:
        print(f"   ❌ {'Dry-run failed' if dry_run else 'Push failed'}!")
        if "rejected" in stderr.lower(): print("   💡 Используй Pull перед Push")
        elif "could not resolve" in stderr.lower(): print("   💡 Проверь интернет и remote URL")
        elif "denied" in stderr.lower(): print("   💡 Проверь права доступа (SSH/PAT)")
        print(f"   Error: {stderr}"); return False

def pull_changes(root, branch=None):
    if not branch: branch = get_branch(root)
    print(f"\n📥 Pulling from origin/{branch}...")
    stdout, stderr, code = run(["git", "pull", "origin", branch], cwd=root)
    if code == 0: print(f"   ✅ Pull successful!"); return True
    else: print(f"   ❌ Pull failed: {stderr}"); return False

def stash_changes(root, message=None):
    if not message: message = f"stash-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    stdout, _, code = run(["git", "stash", "push", "-m", message], cwd=root)
    if code == 0: print(f"   📦 Stashed: {message}"); return True
    else: print("   ℹ️  Nothing to stash"); return False

def setup_remote(root, url):
    stdout, _, code = run(["git", "remote", "get-url", "origin"], cwd=root)
    if code == 0: print(f"   📝 Updating remote: {url}"); run(["git", "remote", "set-url", "origin", url], cwd=root, check=True)
    else: print(f"   📝 Adding remote: {url}"); run(["git", "remote", "add", "origin", url], cwd=root, check=True)
    print("   ✅ Remote configured")

def show_menu(root):
    branch = get_branch(root); remote = get_git_remote(root); status = git_status(root)
    print("\n" + "=" * 60); print("  🚀 CRYPTO BOT GITHUB UPDATER v2.3"); print("=" * 60)
    print(f"  📁 Project: {root}"); print(f"  🌿 Branch:  {branch}"); print(f"  🌐 Remote:  {remote or 'не настроен'}")
    print("-" * 60)
    if status["has_changes"]: print(f"  📋 Changes: {len(status['modified'])} modified, {len(status['untracked'])} new, {len(status['deleted'])} deleted, {len(status['staged'])} staged")
    else: print("  ✅ No changes")
    print("-" * 60)
    print("""
  ┌─────────────────────────────────────────────────────────┐
  │  [1] 📊 Status (with fetch)                             │
  │  [2] ➕ Add all (git add -A)                            │
  │  [3] 💾 Commit                                          │
  │  [4] 🚀 Push to GitHub                                  │
  │  [5] ⚡ Quick update (add + commit + push)              │
  │  [6] 📥 Pull from GitHub                                │
  │  [7] 📦 Stash                                           │
  │  [8] 🔗 Setup remote                                    │
  │  [9] 🧹 Clear screen                                    │
  │  [0] ❌ Exit                                            │
  └─────────────────────────────────────────────────────────┘
    """)
    try: choice = input("  Выбери действие [0-9]: ").strip()
    except (EOFError, KeyboardInterrupt): print("\n"); return "0"
    return choice

def handle_menu(root):
    while True:
        choice = show_menu(root)
        if choice == "0": print("\n👋 До свидания!"); break
        elif choice == "1": show_status(root); input("\n  Нажми Enter...")
        elif choice == "2": print("\n➕ Adding all..."); add_files(root); input("\n  Нажми Enter...")
        elif choice == "3":
            print("\n💾 Committing..."); status = git_status(root)
            if not status["has_changes"] and not status["staged"]: print("   ℹ️  Nothing to commit.")
            else:
                if status["has_changes"] and not status["staged"]: add_files(root)
                msg = input("  Commit message: ").strip() or f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                commit_changes(root, msg)
            input("\n  Нажми Enter...")
        elif choice == "4": print("\n🚀 Pushing..."); push_changes(root); input("\n  Нажми Enter...")
        elif choice == "5":
            print("\n⚡ Quick update..."); show_status(root); status = git_status(root)
            if not status["has_changes"] and not status["staged"]: print("\nℹ️  No local changes."); push_changes(root)
            else:
                add_files(root)
                msg = input("  Commit message: ").strip() or f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                if commit_changes(root, msg): push_changes(root)
            input("\n  Нажми Enter...")
        elif choice == "6": print("\n📥 Pulling..."); pull_changes(root); input("\n  Нажми Enter...")
        elif choice == "7": print("\n📦 Stashing..."); stash_changes(root); input("\n  Нажми Enter...")
        elif choice == "8": print("\n🔗 Setup remote..."); url = input("  URL: ").strip()
                if url: setup_remote(root, url)
            input("\n  Нажми Enter...")
        elif choice == "9": os.system("cls" if os.name == "nt" else "clear")
        else: print("\n❌ Invalid choice."); input("  Нажми Enter...")

def main():
    parser = argparse.ArgumentParser(description="CryptoBot GitHub Updater v2.3")
    parser.add_argument("--status", "-s", action="store_true")
    parser.add_argument("--commit", "-c", metavar="MSG")
    parser.add_argument("--push", "-p", action="store_true")
    parser.add_argument("--force", "-f", action="store_true")
    parser.add_argument("--pull", action="store_true")
    parser.add_argument("--stash", action="store_true")
    parser.add_argument("--add", "-a", nargs="*", metavar="FILE")
    parser.add_argument("--all", metavar="MSG")
    parser.add_argument("--setup", metavar="URL")
    parser.add_argument("--branch", "-b", metavar="BRANCH")
    parser.add_argument("--menu", "-m", action="store_true")
    parser.add_argument("--dry-run", "-n", action="store_true")
    args = parser.parse_args()
    check_git_installed()
    root = get_project_root()
    if not ensure_git_repo(root): sys.exit(1)
    has_cli = any([args.status, args.commit, args.push, args.pull, args.stash,
                   args.add is not None, args.all, args.setup, args.dry_run])
    if args.menu or not has_cli: handle_menu(root); return 0
    print(f"📁 Project root: {root}")
    if args.setup: setup_remote(root, args.setup); return 0
    if args.status: show_status(root)
    if args.stash: stash_changes(root)
    if args.pull: pull_changes(root, args.branch)
    if args.all:
        show_status(root); status = git_status(root)
        if not status["has_changes"] and not status["staged"]:
            print("\nℹ️  No changes.")
            if args.push or args.force or args.dry_run: push_changes(root, force=args.force, branch=args.branch, dry_run=args.dry_run)
            return 0
        add_files(root)
        if commit_changes(root, args.all): push_changes(root, force=args.force, branch=args.branch, dry_run=args.dry_run)
        return 0
    if args.add is not None: add_files(root, args.add)
    if args.commit:
        if args.add is None:
            s = git_status(root)
            if s["has_changes"] or s["staged"]: add_files(root)
        commit_changes(root, args.commit)
    if args.push or args.force or args.dry_run: push_changes(root, force=args.force, branch=args.branch, dry_run=args.dry_run)
    return 0

if __name__ == "__main__": sys.exit(main())
