#!/usr/bin/env python3
"""
Git Helper v2.1 — исправленная версия
Не путает UI-файлы (config.py, logs.py) с секретами.
"""
import os
import sys
import subprocess
import re
from datetime import datetime
from pathlib import Path


def run_git(args, capture=True, cwd=None):
    """Выполняет команду git."""
    try:
        if capture:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd
            )
            return result.returncode == 0, result.stdout + result.stderr
        else:
            subprocess.run(["git"] + args, check=True, cwd=cwd)
            return True, ""
    except Exception as e:
        return False, str(e)


def find_project_root():
    """Находит корень git-репозитория."""
    start = Path(__file__).parent.resolve()
    current = start
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    if (start / ".git").exists():
        return start
    return None


def get_gitignore_rules(project_root):
    """Читает .gitignore и возвращает список правил."""
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        return []
    rules = []
    for line in gitignore.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rules.append(line)
    return rules


def is_ignored_by_gitignore(filepath, rules):
    """Проверяет, попадает ли файл под правила .gitignore."""
    fp = Path(filepath)
    parts = fp.parts
    name = fp.name

    for rule in rules:
        rule = rule.strip()
        if not rule:
            continue

        # Исключение с ! — файл НЕ игнорируется
        if rule.startswith("!"):
            exc_rule = rule[1:]
            if name == exc_rule or str(fp).replace("\\", "/") == exc_rule:
                return False
            for part in parts:
                if part == exc_rule:
                    return False
            continue

        # Папка (заканчивается на /)
        if rule.endswith("/"):
            folder = rule[:-1]
            # Точное совпадение папки в пути
            for part in parts:
                if part == folder:
                    return True
            # Путь начинается с папки
            if str(fp).replace("\\", "/").startswith(folder + "/"):
                return True

        # wildcard
        if rule.startswith("*"):
            if name.endswith(rule[1:]):
                return True

        # Точное совпадение имени или пути
        if name == rule or str(fp).replace("\\", "/") == rule:
            return True

        # Папка в пути
        for part in parts:
            if part == rule:
                return True

    return False


def looks_sensitive(filepath, project_root):
    """Проверяет, содержит ли файл конфиденциальные данные.

    ИСПРАВЛЕНО v2.1:
    - Не ловит config.py (UI-файл)
    - Не ловит logs.py (UI-файл)
    - Ловит ТОЛЬКО файлы с ключами/секретами
    """
    fp = project_root / filepath
    if not fp.exists() or fp.is_dir():
        return False

    # Проверяем расширение (кэш, логи)
    if filepath.endswith((".pyc", ".pyo", ".cache", ".db", ".sqlite3")):
        return True

    # ИМЯ ФАЙЛА — точные совпадения для секретов
    name_lower = fp.name.lower()
    secret_names = [
        "user_config.json",
        "bot_config.json",  # только если содержит ключи
        "secrets.json",
        "api_keys.json",
        ".env",
        ".env.local",
    ]

    # Точное совпадение имени
    if name_lower in secret_names:
        # Проверяем содержимое на наличие ключей
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")[:5000]
            if re.search(r'["\']?[A-Za-z0-9]{20,}["\']?', content):
                return True
        except:
            pass
        return True  # Даже если не прочитали — имя говорит само за себя

    # Проверяем содержимое для файлов с подозрительными именами
    lower_path = filepath.lower()
    suspicious = ["secret", "password", "credential", "private_key", "api_key"]
    for kw in suspicious:
        if kw in lower_path:
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")[:5000]
                if re.search(r'["\']?[A-Za-z0-9]{20,}["\']?', content):
                    return True
            except:
                pass

    # config.py, logs.py и т.д. — НЕ секреты
    return False


def get_changed_files(project_root):
    """Возвращает список измененных файлов со статусом."""
    success, output = run_git(["status", "--porcelain"], cwd=project_root)
    if not success:
        return []

    files = []
    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        status = line[:2].strip()
        filepath = line[3:].strip().strip('"')
        files.append((status, filepath))
    return files


def categorize_files(files, project_root):
    """Разделяет файлы на категории."""
    rules = get_gitignore_rules(project_root)

    categories = {
        "gitignored": [],
        "sensitive": [],
        "cache": [],
        "ok": [],
    }

    for status, filepath in files:
        item = (status, filepath)

        # Проверяем .gitignore
        if is_ignored_by_gitignore(filepath, rules):
            categories["gitignored"].append(item)
            continue

        # Проверяем кэш
        if "__pycache__" in filepath or filepath.endswith((".pyc", ".pyo")):
            categories["cache"].append(item)
            continue

        # Проверяем конфиденциальность
        if looks_sensitive(filepath, project_root):
            categories["sensitive"].append(item)
            continue

        categories["ok"].append(item)

    return categories


def print_file(status, filepath, icon):
    """Красивый вывод файла."""
    status_map = {
        "M": "modified", "A": "added", "D": "deleted", "??": "untracked",
        "R": "renamed", "C": "copied", "U": "updated"
    }
    desc = status_map.get(status, status)
    print(f"   {icon} [{desc:10}] {filepath}")


def ensure_gitignore(project_root):
    """Создает .gitignore с правильными правилами."""
    gitignore = project_root / ".gitignore"

    base_rules = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Environments
.env
.env.local

# Logs (только в корне и все .log файлы)
/logs/
*.log

# IDE
.vscode/
.idea/
*.swp

# Data & Cache
data/cache/
data/models/*.pkl
*.sqlite3
*.db

# Configs with secrets (keep local)
config/user_config.json
config/secrets.json

# НО НЕ игнорируем UI-файлы!
!src/ui/pages/config.py
!src/ui/pages/logs.py
"""

    if not gitignore.exists():
        gitignore.write_text(base_rules, encoding="utf-8")
        print("📝 Создан .gitignore")
        return True

    content = gitignore.read_text(encoding="utf-8")

    # Проверяем и исправляем проблемные правила
    fixes_needed = []

    # Проверяем logs/ без /
    if "logs/" in content and "/logs/" not in content:
        fixes_needed.append("logs/ → /logs/")

    # Проверяем исключения для UI-файлов
    if "!src/ui/pages/config.py" not in content:
        fixes_needed.append("!src/ui/pages/config.py")
    if "!src/ui/pages/logs.py" not in content:
        fixes_needed.append("!src/ui/pages/logs.py")

    if fixes_needed:
        # Заменяем logs/ на /logs/
        content = content.replace("\nlogs/\n", "\n/logs/\n")

        # Добавляем исключения
        if "!src/ui/pages/config.py" not in content:
            content += "\n!src/ui/pages/config.py\n"
        if "!src/ui/pages/logs.py" not in content:
            content += "!src/ui/pages/logs.py\n"

        gitignore.write_text(content, encoding="utf-8")
        print(f"📝 Исправлен .gitignore: {', '.join(fixes_needed)}")
        return True

    return False


def main():
    print("=" * 60)
    print("🐙  GIT HELPER v2.1 — Исправленная отправка на GitHub")
    print("=" * 60)

    project_root = find_project_root()
    if not project_root:
        print("\n❌ Не найден Git-репозиторий")
        input("\nНажмите Enter...")
        sys.exit(1)

    print(f"\n📁 Проект: {project_root}")

    if ensure_gitignore(project_root):
        print("   (.gitignore обновлен)")

    files = get_changed_files(project_root)
    if not files:
        print("\n✅ Нет изменений для отправки.")
        input("\nНажмите Enter...")
        return

    branch_success, branch_out = run_git(["branch", "--show-current"], cwd=project_root)
    branch = branch_out.strip() if branch_success else "main"
    print(f"🌿 Ветка: {branch}")
    print(f"📦 Всего изменений: {len(files)}\n")

    cat = categorize_files(files, project_root)

    if cat["gitignored"]:
        print("⛔  Пропущено (в .gitignore):")
        for status, fp in cat["gitignored"]:
            print_file(status, fp, "  ⛔")
        print()

    if cat["cache"]:
        print("🗑️  Пропущено (кэш/временные):")
        for status, fp in cat["cache"]:
            print_file(status, fp, "  🗑️")
        print()

    if cat["sensitive"]:
        print("🔒  Пропущено (похоже на секреты/ключи):")
        for status, fp in cat["sensitive"]:
            print_file(status, fp, "  🔒")
        print("   💡 Если это НЕ секрет — добавьте в .gitignore правило с !")
        print()

    to_commit = cat["ok"]
    if not to_commit:
        print("⚠️  Нет файлов для отправки.")
        input("\nНажмите Enter...")
        return

    print("✅  Будет отправлено на GitHub:")
    for status, fp in to_commit:
        print_file(status, fp, "  ✅")

    print(f"\n📊 Итого: {len(to_commit)} файлов для коммита")

    print("\n" + "-" * 40)
    print("Выберите действие:")
    print("  [1] Отправить ВСЁ показанное выше")
    print("  [2] Выбрать файлы вручную (по номерам)")
    print("  [3] Отмена")

    choice = input("\n>>> ").strip()

    if choice == "3" or choice.lower() in ("q", "quit"):
        print("❌ Отменено.")
        input("Нажмите Enter...")
        return

    selected = []
    if choice == "2":
        print("\nВведите номера файлов через пробел:")
        for i, (status, fp) in enumerate(to_commit, 1):
            print(f"  [{i}] {fp}")
        nums = input("\n>>> ").strip().split()
        try:
            for n in nums:
                idx = int(n) - 1
                if 0 <= idx < len(to_commit):
                    selected.append(to_commit[idx])
        except:
            print("❌ Неверный ввод.")
            input("Нажмите Enter...")
            return
        if not selected:
            print("❌ Ничего не выбрано.")
            return
    else:
        selected = to_commit

    print("\n➕ Добавляем файлы...")
    for status, fp in selected:
        run_git(["add", fp], cwd=project_root)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n📌 Сообщение коммита (Enter = авто):")
    msg = input(">>> ").strip()
    if not msg:
        msg = f"Update {timestamp}"
    else:
        msg = f"{msg} [{timestamp}]"

    print(f"\n💾 Коммит: {msg}")
    success, out = run_git(["commit", "-m", msg], cwd=project_root)
    if not success:
        if "nothing to commit" in out:
            print("ℹ️ Нечего коммитить.")
            input("Нажмите Enter...")
            return
        print("❌ Ошибка коммита:")
        print(out)
        input("Нажмите Enter...")
        return

    print(f"\n🚀 Отправка в origin/{branch}...")
    success, out = run_git(["push", "origin", branch], capture=False, cwd=project_root)
    if success:
        print("\n" + "=" * 40)
        print("✅ УСПЕШНО ОТПРАВЛЕНО НА GITHUB!")
        print("=" * 40)
        print(f"   📦 Файлов: {len(selected)}")
        print(f"   💬 Коммит: {msg}")
        print(f"   🌿 Ветка:  {branch}")
    else:
        print("\n❌ Ошибка push:")
        print(f"   {out}")

    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()
