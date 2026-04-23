#!/usr/bin/env python3
"""
Git Helper — улучшенная утилита отправки изменений на GitHub
Исключает конфиденциальные файлы (ключи API, кэш, логи)
"""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path


# === ФАЙЛЫ И ПАПКИ, КОТОРЫЕ НИКОГДА НЕ ОТПРАВЛЯЕМ НА GITHUB ===
EXCLUDE_PATTERNS = [
    # Конфиги с ключами
    "config/bot_config.json",
    "config/user_config.json",
    "config/api_keys.json",
    "config/secrets.json",
    ".env",
    ".env.local",

    # Кэш Python
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache/",
    ".mypy_cache/",

    # Логи и данные
    "logs/",
    "log/",
    "data/cache/",
    "data/models/",
    "*.log",

    # Виртуальное окружение
    "venv/",
    ".venv/",
    "env/",

    # IDE
    ".idea/",
    ".vscode/",
    "*.swp",
    "*.swo",

    # Системные
    ".DS_Store",
    "Thumbs.db",

    # Большие файлы
    "*.csv",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
]


def run_git(args, capture=True):
    """Выполняет команду git и возвращает результат."""
    try:
        if capture:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                check=False,
                cwd=PROJECT_ROOT
            )
            return result.returncode == 0, result.stdout + result.stderr
        else:
            subprocess.run(["git"] + args, check=True, cwd=PROJECT_ROOT)
            return True, ""
    except Exception as e:
        return False, str(e)


def get_branch():
    success, branch = run_git(["branch", "--show-current"])
    return branch.strip() if success and branch else "main"


def has_changes():
    """Проверяет, есть ли нескоммиченные изменения."""
    success, output = run_git(["status", "--porcelain"])
    return bool(output.strip())


def get_changed_files():
    """Возвращает список изменённых файлов."""
    success, output = run_git(["status", "--porcelain"])
    if not success:
        return []
    files = []
    for line in output.strip().split("\n"):
        if line:
            status = line[:2]
            filepath = line[3:].strip()
            files.append((status, filepath))
    return files


def is_excluded(filepath):
    """Проверяет, нужно ли исключить файл из коммита."""
    fp_lower = filepath.lower().replace("\\", "/")

    for pattern in EXCLUDE_PATTERNS:
        pattern = pattern.lower().replace("\\", "/")

        # Точное совпадение
        if fp_lower == pattern:
            return True

        # wildcard *.ext
        if pattern.startswith("*."):
            ext = pattern[1:]  # .pyc
            if fp_lower.endswith(ext):
                return True

        # Папка с /
        if pattern.endswith("/"):
            if fp_lower.startswith(pattern) or "/" + pattern in fp_lower:
                return True

    return False


def setup_gitignore():
    """Создаёт/обновляет .gitignore если нужно."""
    gitignore_path = PROJECT_ROOT / ".gitignore"

    needed_rules = [
        "config/bot_config.json",
        "config/user_config.json",
        "__pycache__/",
        "*.pyc",
        "logs/",
        "data/cache/",
        ".env",
        "*.log",
    ]

    existing = ""
    if gitignore_path.exists():
        existing = gitignore_path.read_text(encoding="utf-8")

    added = []
    for rule in needed_rules:
        if rule not in existing:
            added.append(rule)

    if added:
        with open(gitignore_path, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n# Auto-added by git_helper\n")
            for rule in added:
                f.write(rule + "\n")
        print(f"📝 Добавлены правила в .gitignore: {', '.join(added)}")
        return True
    return False


def main():
    global PROJECT_ROOT

    print("🐙 GIT FAST UPDATE — отправляем изменения в GitHub\n")

    # Определяем корень проекта
    script_dir = Path(__file__).parent.resolve()
    PROJECT_ROOT = script_dir

    # Ищем .git вверх по дереву
    while PROJECT_ROOT != PROJECT_ROOT.parent:
        if (PROJECT_ROOT / ".git").exists():
            break
        PROJECT_ROOT = PROJECT_ROOT.parent

    if not (PROJECT_ROOT / ".git").exists():
        print("❌ Не найден Git-репозиторий. Запустите скрипт из папки проекта.")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    print(f"📁 Корень проекта: {PROJECT_ROOT}")

    # Настраиваем .gitignore
    if setup_gitignore():
        print("   (файлы из .gitignore не будут отправлены)\n")

    # Проверяем изменения
    if not has_changes():
        print("✅ Нет изменений для коммита. Всё актуально.")
        input("Нажмите Enter...")
        return

    branch = get_branch()
    print(f"🌿 Ветка: {branch}\n")

    # Показываем что изменилось
    changed = get_changed_files()
    print("📋 Изменённые файлы:")

    included = []
    excluded = []

    for status, filepath in changed:
        status_icon = {
            "M ": "📝", " M": "📝",
            "A ": "➕", " A": "➕",
            "D ": "🗑️", " D": "🗑️",
            "??": "❓",
        }.get(status, "📄")

        if is_excluded(filepath):
            print(f"   ⛔ {status_icon} {filepath}  (исключено — ключи/кэш/логи)")
            excluded.append(filepath)
        else:
            print(f"   ✅ {status_icon} {filepath}")
            included.append(filepath)

    if not included:
        print("\n⚠️ Нет файлов для отправки (все исключены или уже на GitHub).")
        input("Нажмите Enter...")
        return

    print(f"\n📊 Итого: {len(included)} файлов для отправки, {len(excluded)} исключено")

    # Подтверждение
    confirm = input("\n🚀 Отправить на GitHub? (y/n): ").strip().lower()
    if confirm not in ("y", "yes", "д", "да"):
        print("❌ Отменено.")
        input("Нажмите Enter...")
        return

    # Добавляем файлы по одному (чтобы исключить ненужные)
    print("\n➕ Добавляем файлы...")
    for filepath in included:
        run_git(["add", filepath])

    # Формируем сообщение коммита
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n📌 Введите сообщение коммита (Enter = авто):")
    msg = input(">>> ").strip()
    if not msg:
        msg = f"Update bot files {timestamp}"
    else:
        msg = f"{msg} [{timestamp}]"

    # Коммит
    print(f"\n💾 Коммит: {msg}")
    success, out = run_git(["commit", "-m", msg])
    if not success:
        if "nothing to commit" in out:
            print("ℹ️ Нет изменений (уже закоммичено).")
            input("Нажмите Enter...")
            return
        else:
            print("❌ Ошибка коммита:")
            print(out)
            input("Нажмите Enter...")
            return

    # Пуш
    print(f"\n🚀 Отправка в origin/{branch}...")
    success, out = run_git(["push", "origin", branch], capture=False)
    if success:
        print("\n✅ Успешно отправлено на GitHub!")
        print(f"   Файлов: {len(included)}")
        print(f"   Коммит: {msg}")
    else:
        print("\n❌ Ошибка при push.")
        if "authentication" in out.lower():
            print("💡 Проверьте авторизацию GitHub (токен или SSH).")
        elif "rejected" in out.lower():
            print("💡 Возможно, нужно сделать git pull перед push.")

    print("\nГотово.")
    input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()
