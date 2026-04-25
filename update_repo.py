#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CryptoBot GitHub Updater v2.1
Скрипт для обновления репозитория на GitHub с ноутбука.
Поддерживает: интерактивное меню, commit, push, force-push, stash, pull, status.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime


def run(cmd: list, cwd: Path = None, check: bool = False) -> tuple:
    """Выполняет shell-команду и возвращает (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if check and result.returncode != 0:
            print(f"❌ Command failed: {' '.join(cmd)}")
            print(f"   stderr: {result.stderr}")
            sys.exit(1)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except FileNotFoundError as e:
        print(f"❌ Command not found: {cmd[0]} — {e}")
        sys.exit(1)


def get_project_root() -> Path:
    """Находит корень проекта (где есть .git или main.py)."""
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


def ensure_git_repo(root: Path) -> bool:
    """Проверяет, что это git-репозиторий."""
    if not (root / ".git").exists():
        print(f"❌ Не найден .git в {root}")
        print("   Инициализируй репозиторий: git init")
        return False
    return True


def get_git_remote(root: Path) -> str:
    """Получает URL удалённого репозитория (origin)."""
    stdout, _, code = run(["git", "remote", "get-url", "origin"], cwd=root)
    return stdout if code == 0 else ""


def get_branch(root: Path) -> str:
    """Получает текущую ветку."""
    stdout, _, _ = run(["git", "branch", "--show-current"], cwd=root)
    return stdout or "main"


def git_status(root: Path) -> dict:
    """Возвращает статус git-репозитория."""
    stdout, _, _ = run(["git", "status", "--short"], cwd=root)
    modified = []
    untracked = []
    deleted = []
    staged = []

    for line in stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        file_path = line[3:].strip()

        if status.startswith("M") or status.endswith("M"):
            modified.append(file_path)
        elif status.startswith("D") or status.endswith("D"):
            deleted.append(file_path)
        elif status.startswith("A") or status.startswith("?"):
            untracked.append(file_path)
        elif status.startswith(" ") and status[1] in "MAD":
            staged.append(file_path)

    return {
        "modified": modified,
        "untracked": untracked,
        "deleted": deleted,
        "staged": staged,
        "has_changes": bool(stdout.strip())
    }


def show_status(root: Path):
    """Показывает красивый статус репозитория."""
    print("\n📊 Git Status:")
    print("-" * 50)

    stdout, _, _ = run(["git", "status", "-sb"], cwd=root)
    if stdout:
        print(stdout)
    else:
        print("   Репозиторий чист — нет изменений.")

    branch = get_branch(root)
    print(f"\n   🌿 Текущая ветка: {branch}")

    remote = get_git_remote(root)
    if remote:
        print(f"   🌐 Удалённый репозиторий: {remote}")
    else:
        print("   ⚠️  Удалённый репозиторий не настроен")
    print("-" * 50)


def add_files(root: Path, files: list = None):
    """Добавляет файлы в индекс git."""
    if files:
        for f in files:
            full_path = root / f
            if full_path.exists():
                run(["git", "add", f], cwd=root, check=True)
                print(f"   ➕ Added: {f}")
            else:
                print(f"   ⚠️  Not found: {f}")
    else:
        run(["git", "add", "-A"], cwd=root, check=True)
        print("   ➕ Added all changes")


def commit_changes(root: Path, message: str = None):
    """Создаёт коммит."""
    if not message:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        message = f"Update {timestamp}"

    stdout, stderr, code = run(["git", "commit", "-m", message], cwd=root)
    if code == 0:
        hash_short, _, _ = run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
        print(f"   ✅ Committed: [{hash_short}] {message}")
        return True
    elif "nothing to commit" in stderr.lower() or "nothing to commit" in stdout.lower():
        print("   ℹ️  Nothing to commit")
        return False
    else:
        print(f"   ❌ Commit failed: {stderr}")
        return False


def push_changes(root: Path, force: bool = False, branch: str = None):
    """Отправляет изменения на GitHub."""
    if not branch:
        branch = get_branch(root)

    cmd = ["git", "push", "origin", branch]
    if force:
        cmd.insert(2, "--force")
        print(f"\n🚀 Force-pushing to origin/{branch}...")
    else:
        print(f"\n🚀 Pushing to origin/{branch}...")

    stdout, stderr, code = run(cmd, cwd=root)

    if code == 0:
        print(f"   ✅ Push successful!")
        if stdout:
            print(f"   {stdout}")
    else:
        print(f"   ❌ Push failed!")
        if "rejected" in stderr.lower():
            print("   💡 Подсказка: используй Pull для получения изменений с GitHub")
            print("   💡 Или Force Push для принудительного push (осторожно!)")
        print(f"   Error: {stderr}")
        return False
    return True


def pull_changes(root: Path, branch: str = None):
    """Получает изменения с GitHub."""
    if not branch:
        branch = get_branch(root)

    print(f"\n📥 Pulling from origin/{branch}...")
    stdout, stderr, code = run(["git", "pull", "origin", branch], cwd=root)

    if code == 0:
        print(f"   ✅ Pull successful!")
        if stdout:
            print(f"   {stdout}")
    else:
        print(f"   ❌ Pull failed: {stderr}")
        if "conflict" in stderr.lower():
            print("   ⚠️  Конфликты слияния! Разреши их вручную.")
        return False
    return True


def stash_changes(root: Path, message: str = None):
    """Сохраняет изменения в stash."""
    if not message:
        message = f"stash-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    stdout, _, code = run(["git", "stash", "push", "-m", message], cwd=root)
    if code == 0:
        print(f"   📦 Stashed: {message}")
        return True
    else:
        print(f"   ℹ️  Nothing to stash")
        return False


def setup_remote(root: Path, url: str):
    """Настраивает удалённый репозиторий."""
    stdout, _, code = run(["git", "remote", "get-url", "origin"], cwd=root)
    if code == 0:
        print(f"   📝 Updating remote origin: {url}")
        run(["git", "remote", "set-url", "origin", url], cwd=root, check=True)
    else:
        print(f"   📝 Adding remote origin: {url}")
        run(["git", "remote", "add", "origin", url], cwd=root, check=True)
    print("   ✅ Remote configured")


def show_menu(root: Path) -> str:
    """Показывает интерактивное меню и возвращает выбор пользователя."""
    branch = get_branch(root)
    remote = get_git_remote(root)
    status = git_status(root)

    print("\n" + "=" * 60)
    print("  🚀 CRYPTO BOT GITHUB UPDATER v2.1")
    print("=" * 60)
    print(f"  📁 Project: {root}")
    print(f"  🌿 Branch:  {branch}")
    print(f"  🌐 Remote:  {remote or 'не настроен'}")
    print("-" * 60)

    if status["has_changes"]:
        print(f"  📋 Изменения: {len(status['modified'])} modified, "
              f"{len(status['untracked'])} new, {len(status['deleted'])} deleted")
    else:
        print("  ✅ Нет изменений")
    print("-" * 60)

    print("""
  ┌─────────────────────────────────────────────────────────┐
  │  [1] 📊 Статус репозитория                              │
  │  [2] ➕ Добавить все изменения (git add -A)             │
  │  [3] 💾 Создать коммит                                  │
  │  [4] 🚀 Отправить на GitHub (push)                      │
  │  [5] ⚡ Быстрое обновление (add + commit + push)        │
  │  [6] 📥 Получить изменения с GitHub (pull)              │
  │  [7] 📦 Сохранить в stash (отложить изменения)          │
  │  [8] 🔗 Настроить удалённый репозиторий                 │
  │  [9] 🧹 Очистить экран                                  │
  │  [0] ❌ Выход                                           │
  └─────────────────────────────────────────────────────────┘
    """)

    try:
        choice = input("  Выбери действие [0-9]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n")
        return "0"
    return choice


def handle_menu(root: Path):
    """Обрабатывает интерактивное меню."""
    while True:
        choice = show_menu(root)

        if choice == "0":
            print("\n👋 До свидания!")
            break

        elif choice == "1":
            show_status(root)

        elif choice == "2":
            print("\n➕ Добавление всех изменений...")
            add_files(root)
            input("\n  Нажми Enter для продолжения...")

        elif choice == "3":
            print("\n💾 Создание коммита...")
            status = git_status(root)
            if not status["has_changes"] and not status["staged"]:
                print("   ℹ️  Нет изменений для коммита.")
            else:
                if status["has_changes"] and not status["staged"]:
                    add_files(root)
                msg = input("  Сообщение коммита: ").strip()
                if not msg:
                    msg = f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                commit_changes(root, msg)
            input("\n  Нажми Enter для продолжения...")

        elif choice == "4":
            print("\n🚀 Отправка на GitHub...")
            push_changes(root)
            input("\n  Нажми Enter для продолжения...")

        elif choice == "5":
            print("\n⚡ Быстрое обновление (add + commit + push)...")
            show_status(root)
            status = git_status(root)
            if not status["has_changes"]:
                print("\nℹ️  Нет изменений для коммита.")
                push_changes(root)
            else:
                add_files(root)
                msg = input("  Сообщение коммита: ").strip()
                if not msg:
                    msg = f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                if commit_changes(root, msg):
                    push_changes(root)
            input("\n  Нажми Enter для продолжения...")

        elif choice == "6":
            print("\n📥 Получение изменений с GitHub...")
            pull_changes(root)
            input("\n  Нажми Enter для продолжения...")

        elif choice == "7":
            print("\n📦 Сохранение изменений в stash...")
            stash_changes(root)
            input("\n  Нажми Enter для продолжения...")

        elif choice == "8":
            print("\n🔗 Настройка удалённого репозитория...")
            url = input("  URL репозитория (например https://github.com/user/repo.git): ").strip()
            if url:
                setup_remote(root, url)
            else:
                print("   ⚠️  URL не указан")
            input("\n  Нажми Enter для продолжения...")

        elif choice == "9":
            os.system("cls" if os.name == "nt" else "clear")

        else:
            print("\n❌ Неверный выбор. Попробуй снова.")
            input("  Нажми Enter для продолжения...")


def main():
    parser = argparse.ArgumentParser(
        description="CryptoBot GitHub Updater — обновление репозитория",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ИНТЕРАКТИВНЫЙ РЕЖИМ:
  Запусти без аргументов для меню:
      python update_repo.py

КОМАНДНЫЙ РЕЖИМ:
  python update_repo.py --status              # Показать статус
  python update_repo.py --commit "Fix bugs"   # Закоммитить
  python update_repo.py --push                # Отправить на GitHub
  python update_repo.py --all "v9.1 fixes"    # Add + Commit + Push
  python update_repo.py --pull                # Получить с GitHub
  python update_repo.py --setup https://...   # Настроить репо
        """
    )

    parser.add_argument("--status", "-s", action="store_true",
                        help="Показать статус репозитория")
    parser.add_argument("--commit", "-c", metavar="MSG",
                        help="Создать коммит с сообщением")
    parser.add_argument("--push", "-p", action="store_true",
                        help="Отправить изменения на GitHub")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Принудительный push")
    parser.add_argument("--pull", action="store_true",
                        help="Получить изменения с GitHub")
    parser.add_argument("--stash", action="store_true",
                        help="Сохранить изменения в stash")
    parser.add_argument("--add", "-a", nargs="*", metavar="FILE",
                        help="Добавить файлы (без аргументов — все)")
    parser.add_argument("--all", metavar="MSG",
                        help="Add + Commit + Push одной командой")
    parser.add_argument("--setup", metavar="URL",
                        help="Настроить удалённый репозиторий")
    parser.add_argument("--branch", "-b", metavar="BRANCH",
                        help="Указать ветку")
    parser.add_argument("--menu", "-m", action="store_true",
                        help="Показать интерактивное меню")

    args = parser.parse_args()

    root = get_project_root()

    if not ensure_git_repo(root):
        sys.exit(1)

    # Если нет аргументов или --menu — показываем интерактивное меню
    has_cli_args = any([
        args.status, args.commit, args.push, args.pull,
        args.stash, args.add is not None, args.all, args.setup
    ])

    if args.menu or not has_cli_args:
        handle_menu(root)
        return 0

    # CLI режим
    print(f"📁 Project root: {root}")

    if args.setup:
        setup_remote(root, args.setup)
        return 0

    if args.status:
        show_status(root)

    if args.stash:
        print("\n📦 Stashing changes...")
        stash_changes(root)

    if args.pull:
        pull_changes(root, args.branch)

    if args.all:
        print("\n🔄 Running full update cycle...")
        show_status(root)
        status = git_status(root)
        if not status["has_changes"]:
            print("\nℹ️  Нет изменений для коммита.")
            if args.push or args.force:
                push_changes(root, force=args.force, branch=args.branch)
            return 0
        add_files(root)
        if commit_changes(root, args.all):
            push_changes(root, force=args.force, branch=args.branch)
        return 0

    if args.add is not None:
        print("\n➕ Adding files...")
        if args.add:
            add_files(root, args.add)
        else:
            add_files(root)

    if args.commit:
        if args.add is None:
            status = git_status(root)
            if status["has_changes"]:
                add_files(root)
        commit_changes(root, args.commit)

    if args.push or args.force:
        push_changes(root, force=args.force, branch=args.branch)

    return 0


if __name__ == "__main__":
    sys.exit(main())
