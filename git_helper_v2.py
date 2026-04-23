#!/usr/bin/env python3
"""
Git Helper v2 — универсальная утилита отправки на GitHub
Не зависит от конкретных имен файлов. Читает .gitignore,
авто-определяет конфиденциальные файлы по содержимому,
дает интерактивный выбор перед отправкой.
"""
import os
import sys
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path


# === МИНИМАЛЬНЫЙ БАЗОВЫЙ СПИСОК (только если .gitignore пустой) ===
SENSITIVE_PATTERNS = [
    r'api[_\-]?key',
    r'secret[_\-]?key',
    r'private[_\-]?key',
    r'password',
    r'token',
    r'\b[A-Za-z0-9]{32,}\b',  # длинные строки — возможно ключи
]


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
    # Fallback: если скрипт в корне
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

        # Папка (заканчивается на /)
        if rule.endswith("/"):
            folder = rule[:-1]
            for part in parts:
                if part == folder or part.startswith(folder):
                    return True

        # wildcard
        if rule.startswith("*"):
            if name.endswith(rule[1:]):  # *.pyc
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
    """Проверяет, содержит ли файл конфиденциальные данные."""
    fp = project_root / filepath
    if not fp.exists() or fp.is_dir():
        return False

    # Проверяем расширение
    if filepath.endswith((".pyc", ".pyo", ".log", ".cache", ".db", ".sqlite3")):
        return True

    # Проверяем имя
    lower_name = filepath.lower()
    keywords = ["config", "secret", "key", "token", "password", "credential", ".env"]
    for kw in keywords:
        if kw in lower_name:
            # Проверяем содержимое
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")[:5000]
                # Ищем JSON с ключами
                if "api_key" in content.lower() or "secret" in content.lower():
                    return True
                # Ищем длинные строки (возможно ключи)
                if re.search(r'["\']?[A-Za-z0-9]{32,}["\']?', content):
                    return True
            except:
                pass

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
        "gitignored": [],      # Уже в .gitignore
        "sensitive": [],       # Похоже на ключи/секреты
        "cache": [],           # Кэш Python
        "ok": [],              # Безопасные для отправки
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


def print_file(status, filepath, icon, color=""):
    """Красивый вывод файла."""
    status_map = {
        "M": "modified", "A": "added", "D": "deleted", "??": "untracked",
        "R": "renamed", "C": "copied", "U": "updated"
    }
    desc = status_map.get(status, status)
    print(f"   {icon} [{desc:10}] {filepath}")


def ensure_gitignore(project_root):
    """Создает .gitignore с базовыми правилами если его нет."""
    gitignore = project_root / ".gitignore"

    base_rules = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Environments
.env
.venv
env/
venv/

# Logs
*.log
logs/

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
"""

    if not gitignore.exists():
        gitignore.write_text(base_rules, encoding="utf-8")
        print("📝 Создан .gitignore с базовыми правилами")
        return True

    # Проверяем, есть ли ключевые правила
    content = gitignore.read_text(encoding="utf-8")
    missing = []
    for rule in ["__pycache__/", ".env", "*.log", "config/user_config.json"]:
        if rule not in content:
            missing.append(rule)

    if missing:
        with open(gitignore, "a", encoding="utf-8") as f:
            if not content.endswith("\n"):
                f.write("\n")
            f.write("\n# Auto-added by git_helper\n")
            for rule in missing:
                f.write(rule + "\n")
        print(f"📝 Добавлены правила в .gitignore: {', '.join(missing)}")
        return True

    return False


def main():
    print("=" * 60)
    print("🐙  GIT HELPER v2 — Универсальная отправка на GitHub")
    print("=" * 60)

    # Находим проект
    project_root = find_project_root()
    if not project_root:
        print("\n❌ Не найден Git-репозиторий (.git папка)")
        print("   Запустите скрипт из папки проекта.")
        input("\nНажмите Enter...")
        sys.exit(1)

    print(f"\n📁 Проект: {project_root}")

    # Проверяем .gitignore
    if ensure_gitignore(project_root):
        print("   (перезапустите скрипт если добавились новые правила)")

    # Получаем изменения
    files = get_changed_files(project_root)
    if not files:
        print("\n✅ Нет изменений для отправки. Все актуально!")
        input("\nНажмите Enter...")
        return

    branch_success, branch_out = run_git(["branch", "--show-current"], cwd=project_root)
    branch = branch_out.strip() if branch_success else "main"
    print(f"🌿 Ветка: {branch}")
    print(f"📦 Всего изменений: {len(files)}\n")

    # Категоризируем
    cat = categorize_files(files, project_root)

    # Выводим
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
        print("⚠️  Нет файлов для отправки (все исключены или в .gitignore).")
        print("   Проверьте .gitignore или добавьте файлы вручную через git add")
        input("\nНажмите Enter...")
        return

    print("✅  Будет отправлено на GitHub:")
    for status, fp in to_commit:
        print_file(status, fp, "  ✅")

    print(f"\n📊 Итого: {len(to_commit)} файлов для коммита")
    print(f"   Пропущено: {len(cat['gitignored']) + len(cat['cache']) + len(cat['sensitive'])}")

    # Выбор действия
    print("\n" + "-" * 40)
    print("Выберите действие:")
    print("  [1] Отправить ВСЁ показанное выше")
    print("  [2] Выбрать файлы вручную (по номерам)")
    print("  [3] Отмена")

    choice = input("\n>>> ").strip()

    if choice == "3" or choice.lower() in ("q", "quit", "н"):
        print("❌ Отменено.")
        input("Нажмите Enter...")
        return

    selected = []
    if choice == "2":
        print("\nВведите номера файлов через пробел (например: 1 3 5)")
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

    # Добавляем выбранные файлы
    print("\n➕ Добавляем файлы...")
    for status, fp in selected:
        run_git(["add", fp], cwd=project_root)

    # Сообщение коммита
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n📌 Сообщение коммита (Enter = авто):")
    msg = input(">>> ").strip()
    if not msg:
        msg = f"Update {timestamp}"
    else:
        msg = f"{msg} [{timestamp}]"

    # Коммит
    print(f"\n💾 Коммит: {msg}")
    success, out = run_git(["commit", "-m", msg], cwd=project_root)
    if not success:
        if "nothing to commit" in out:
            print("ℹ️ Нечего коммитить (возможно, файлы уже в индексе).")
            input("Нажмите Enter...")
            return
        print("❌ Ошибка коммита:")
        print(out)
        input("Нажмите Enter...")
        return

    # Пуш
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
        if "rejected" in out.lower():
            print("   💡 Сделайте git pull перед push")
        elif "authentication" in out.lower():
            print("   💡 Проверьте авторизацию GitHub")
        else:
            print(f"   {out}")

    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()
