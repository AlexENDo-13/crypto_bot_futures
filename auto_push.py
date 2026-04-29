#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CryptoBot Auto-Pusher v1.3 — One command to update repository.
Fixed: handles git status parsing, uses git add -A with .gitignore for backups.
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

def ensure_gitignore(root):
    """Ensure backups/ is in .gitignore"""
    gitignore = root / ".gitignore"
    content = ""
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
    if "backups/" not in content and "backups\\" not in content:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write("\n# Auto-pusher exclusions\n")
            f.write("backups/\n")
            f.write("*.bak\n")
            f.write("*.pyc\n")
            f.write("__pycache__/\n")
        print("   📝 Added backups/ to .gitignore")
        return True
    return False

def main():
    check_git_installed()
    root = get_project_root()

    if not (root / ".git").exists():
        print("❌ Это не git-репозиторий!")
        sys.exit(1)

    branch = get_branch(root)
    print("=" * 60)
    print("  🚀 CRYPTO BOT AUTO-PUSHER v1.3")
    print("=" * 60)
    print(f"  📁 Project: {root}")
    print(f"  🌿 Branch:  {branch}")
    print()

    # Ensure .gitignore has backups/
    print("📝 Checking .gitignore...")
    if ensure_gitignore(root):
        print("   ✅ .gitignore updated")
    else:
        print("   ✅ .gitignore OK")
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

    print(f"   📋 Git status output:\n{stdout}")
    print()

    # Step 2: Add ALL changes (backups are excluded by .gitignore)
    print("➕ Step 2/4: Adding all changes...")
    _, stderr, code = run(["git", "add", "-A"], cwd=root)
    if code == 0:
        print("   ✅ All changes added.")
    elif "LF will be replaced by CRLF" in stderr:
        print("   ✅ All changes added (with LF warning).")
    else:
        print(f"   ⚠️ Add warning: {stderr}")
        print("   Continuing anyway...")

    # Step 3: Commit
    print("\n💾 Step 3/4: Committing...")
    msg = f"Auto-update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    stdout, stderr, code = run(["git", "commit", "-m", msg], cwd=root)
    if code == 0:
        h, _, _ = run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
        print(f"   ✅ Committed: [{h}] {msg}")
    elif "nothing to commit" in (stderr + stdout).lower():
        print("   ℹ️  Nothing to commit.")
        print("\n🚀 Step 4/4: Pushing to GitHub...")
        stdout, stderr, code = run(["git", "push", "origin", branch], cwd=root)
        if code == 0:
            print("   ✅ Push successful!")
        else:
            print(f"   ❌ Push failed: {stderr}")
        print("\n" + "=" * 60)
        print("  DONE")
        print("=" * 60)
        return 0
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
