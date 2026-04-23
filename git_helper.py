#!/usr/bin/env python3
"""
Git Helper — утилита быстрой отправки изменений на GitHub
Запустите двойным кликом или через VS Code.
"""
import os
import sys
import subprocess
from datetime import datetime


def run_git(args, capture=True):
    """Выполняет команду git и возвращает результат."""
    try:
        if capture:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0, result.stdout + result.stderr
        else:
            subprocess.run(["git"] + args, check=True)
            return True, ""
    except subprocess.CalledProcessError as e:
        return False, str(e)


def get_branch():
    success, branch = run_git(["branch", "--show-current"])
    return branch.strip() if success and branch else "main"


def has_changes():
    """Проверяет, есть ли нескоммиченные изменения."""
    success, output = run_git(["status", "--porcelain"])
    return bool(output.strip())


def main():
    print("🐙 GIT FAST UPDATE — отправляем изменения в GitHub\n")

    # Проверяем, что находимся в репозитории
    success, _ = run_git(["rev-parse", "--show-toplevel"])
    if not success:
        print("❌ Не найден Git-репозиторий. Запустите скрипт из папки проекта.")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    if not has_changes():
        print("✅ Нет изменений для коммита. Выход.")
        input("Нажмите Enter...")
        return

    branch = get_branch()
    print(f"📁 Ветка: {branch}")

    # Добавляем все изменения
    print("➕ Добавляем файлы...")
    run_git(["add", "-A"])

    # Формируем сообщение коммита
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("\n📌 Введите сообщение коммита (Enter = авто):")
    msg = input(">>> ").strip()
    if not msg:
        msg = f"Update {timestamp}"
    else:
        msg = f"{msg} [{timestamp}]"

    # Коммит
    print(f"💾 Коммит: {msg}")
    success, out = run_git(["commit", "-m", msg])
    if not success:
        if "nothing to commit" in out:
            print("ℹ️ Нет изменений (уже закоммичено).")
        else:
            print("❌ Ошибка коммита:")
            print(out)
            input("Нажмите Enter...")
            return

    # Пуш
    print(f"🚀 Отправка в origin/{branch}...")
    success, out = run_git(["push", "origin", branch], capture=False)
    if success:
        print("✅ Успешно отправлено на GitHub!")
    else:
        print("❌ Ошибка при push. Проверьте подключение или авторизацию.")
        if "authentication" in out.lower():
            print("💡 Возможно, нужно ввести токен GitHub.")

    print("\nГотово.")
    input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()
