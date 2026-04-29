#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CryptoBot Auto-Pusher v1.1 — One command to update repository.
Fixed: excludes backups/ folder to avoid 'Filename too long' errors.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

def run(cmd, cwd=None, check=False):
    try:
        result = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            print(f"❌ Command failed: {' '.join(cmd)}")
            print(f"   stderr: {result.stderr}")
            sys.exit(1)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except FileNotFoundError as e:
        print(f"❌ Command not found: {cmd[0]} — {e}")
        sys.exit(1)

def check_git_installed():
    if not shutil.which("git"):
        print("❌ Git не найден в PATH.")
        sys.exit(1)

def get_project_root():
    script_dir = Path(__file__).parent.resolve()
    if (script_dir / ".git").exists():
        return script_dir
    for parent in script_dir.parents:
        if (parent / ".git").exists():
            return parent
    if (script_dir / "main.py").exists():
        return script_dir
    for parent in script_dir.parents:
        if (parent / "main.py").exists():
            return parent
    return script_dir

def get_branch(root):
    stdout, _, _ = run(["git", "branch", "--show-current"], cwd=root)
    return stdout or "main"

def add_files_safe(root):
    """Add files excluding backups/ and other junk folders."""
    # First, remove backups from git index if they were added before
    run(["git", "rm", "-r", "--cached", "backups/"], cwd=root)

    # Add specific folders instead of -A
    folders_to_add = [
        "src/", "config/", "main.py", "requirements.txt",
        "setup.py", "README.md", "QUICK_START.md",
        "cleanup_repo.py", "update_repo.py", "auto_push.py", "auto_push.bat"
    ]

    added = False
    for folder in folders_to_add:
        path = root / folder
        if path.exists():
            _, stderr, code = run(["git", "add", folder], cwd=root)
            if code == 0:
                added = True
            elif "LF will be replaced by CRLF" in stderr:
                added = True  # This is just a warning

    if not added:
        # Fallback: add all but exclude backups
        _, stderr, code = run(["git", "add", ".", ":!backups/"], cwd=root)
        if code != 0 and "Filename too long" not in stderr:
            print(f"   ⚠️ Add warning: {stderr}")

    print("   ✅ Changes added (backups excluded).")

def main():
    check_git_installed()
    root = get_project_root()

    if not (root / ".git").exists():
        print("❌ Это не git-репозиторий!")
        sys.exit(1)

    branch = get_branch(root)
    print("=" * 60)
    print("  🚀 CRYPTO BOT AUTO-PUSHER v1.1")
    print("=" * 60)
    print(f"  📁 Project: {root}")
    print(f"  🌿 Branch:  {branch}")
    print()

    # Step 1: Check status
    print("📊 Step 1/4: Checking git status...")
    stdout, _, _ = run(["git", "status", "--short"], cwd=root)
    if not stdout.strip():
        print("   ✅ No changes to commit.")
        print("\n🚀 Step 4/4: Pushing to GitHub...")
        stdout, stderr, code = run(["git", "push", "origin", branch], cwd=root)
        if code == 0:
            print("   ✅ Push successful! (no new changes)")
        else:
            print(f"   ❌ Push failed: {stderr}")
        print("\n" + "=" * 60)
        print("  DONE")
        print("=" * 60)
        return 0

    print(f"   📋 Found changes:")
    for line in stdout.splitlines():
        print(f"      {line}")

    # Step 2: Add all (safe - excludes backups)
    print("\n➕ Step 2/4: Adding changes (excluding backups)...")
    add_files_safe(root)

    # Step 3: Commit
    print("\n💾 Step 3/4: Committing...")
    msg = f"Auto-update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    stdout, stderr, code = run(["git", "commit", "-m", msg], cwd=root)
    if code == 0:
        h, _, _ = run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
        print(f"   ✅ Committed: [{h}] {msg}")
    elif "nothing to commit" in (stderr + stdout).lower():
        print("   ℹ️  Nothing to commit.")
    else:
        print(f"   ❌ Commit failed: {stderr}")
        sys.exit(1)

    # Step 4: Push
    print("\n🚀 Step 4/4: Pushing to GitHub...")
    stdout, stderr, code = run(["git", "push", "origin", branch], cwd=root)
    if code == 0:
        print("   ✅ Push successful!")
    else:
        print(f"   ❌ Push failed!")
        if "rejected" in stderr.lower():
            print("   💡 Используй Pull перед Push")
        elif "could not resolve" in stderr.lower():
            print("   💡 Проверь интернет и remote URL")
        elif "denied" in stderr.lower():
            print("   💡 Проверь права доступа (SSH/PAT)")
        print(f"   Error: {stderr}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ✅ REPOSITORY UPDATED SUCCESSFULLY!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
