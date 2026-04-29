"""
Auto Push v2.1 – безопасная отправка в GitHub с авто-датой.
Запустите: python auto_push.py [-m "сообщение"] [--branch main]
"""

import subprocess
import sys
import os
from datetime import datetime

# Файлы, которые категорически запрещено отправлять
FORBIDDEN_FILES = [
    "test_keys.py",
    "test_bingx_api.py",
    "bingx_api_test.py",
    "test_signature.py",
    "project_base64.txt",
]

def run_git(command, cwd=".", capture_output=True):
    """Выполняет git-команду и возвращает returncode, stdout, stderr."""
    try:
        result = subprocess.run(
            ["git"] + command,
            capture_output=capture_output,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            errors="replace"
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        print(f"Ошибка запуска git: {e}")
        return 1, "", str(e)

def check_forbidden_files():
    """Проверяет, есть ли в рабочем каталоге запрещённые файлы."""
    found = [f for f in FORBIDDEN_FILES if os.path.exists(f)]
    if found:
        print("❌ ОБНАРУЖЕНЫ ЗАПРЕЩЁННЫЕ ФАЙЛЫ:")
        for f in found:
            print(f"   - {f}")
        print("Удалите их или переместите за пределы репозитория перед коммитом.")
        return False
    return True

def get_auto_message():
    """Генерирует сообщение коммита по текущей дате и времени."""
    now = datetime.now()
    return f"Auto-update {now.strftime('%Y-%m-%d %H:%M')}"

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Безопасная отправка в GitHub с авто-сообщением")
    parser.add_argument("-m", "--message", default=None, help="Сообщение коммита (если не указано – генерируется автоматически)")
    parser.add_argument("--branch", default="main", help="Ветка для пуша (по умолчанию main)")
    args = parser.parse_args()

    message = args.message if args.message else get_auto_message()

    # Проверка, что находимся в git-репозитории
    ret, _, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    if ret != 0:
        print("❌ Текущая папка не является Git-репозиторием.")
        sys.exit(1)

    # Проверка на запрещённые файлы
    if not check_forbidden_files():
        sys.exit(1)

    # Добавляем все изменения
    print("[1/3] git add -A ...")
    ret, out, err = run_git(["add", "-A"])
    if ret != 0:
        print(f"❌ Ошибка git add: {err}")
        sys.exit(1)

    # Коммит
    print(f"[2/3] Коммит: \"{message}\"")
    ret, out, err = run_git(["commit", "-m", message])
    if ret != 0:
        if "nothing to commit" in (out + err).lower():
            print("⚠️  Нечего коммитить. Пуш не требуется.")
            sys.exit(0)
        else:
            print(f"❌ Ошибка коммита: {err}")
            sys.exit(1)

    # Пуш
    print(f"[3/3] Пуш в origin/{args.branch} ...")
    ret, out, err = run_git(["push", "origin", args.branch])
    if ret != 0:
        print(f"❌ Ошибка пуша: {err}")
        sys.exit(1)

    print("✅ Успешно отправлено на GitHub!")

if __name__ == "__main__":
    main()
