#!/usr/bin/env python3
"""
Автоматический пуш текущих изменений на GitHub.
Использует git через subprocess, дополнительные библиотеки НЕ нужны.
Запуск: python push_to_github.py [-m "сообщение коммита"] [-b ветка]
"""

import subprocess
import sys
import argparse

def run_git(cmd: list, cwd: str = "."):
    """Выполняет git-команду и возвращает stdout или печатает ошибку."""
    try:
        res = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode != 0:
            print(f"❌ Ошибка git {' '.join(cmd)}: {res.stderr.strip()}")
            return None
        return res.stdout.strip()
    except FileNotFoundError:
        print("❌ Git не найден. Убедитесь, что git установлен и доступен в PATH.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Быстрый пуш изменений в GitHub")
    parser.add_argument("-m", "--message", default="Auto-update from notebook",
                        help="Сообщение коммита")
    parser.add_argument("-b", "--branch", default=None,
                        help="Ветка для пуша (по умолчанию — текущая)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Только показать, что будет запушено, без реальных действий")
    args = parser.parse_args()

    # 1. Проверяем, есть ли неприменённые изменения
    status = run_git(["status", "--porcelain"])
    if status is None:
        print("❌ Не удалось проверить статус репозитория.")
        sys.exit(1)
    if not status:
        print("✅ Нет изменений для коммита — всё уже актуально.")
        return

    # 2. Определяем текущую ветку, если не задана явно
    if not args.branch:
        current_branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if not current_branch:
            print("❌ Не удалось определить текущую ветку.")
            sys.exit(1)
        args.branch = current_branch
        print(f"ℹ️  Текущая ветка: {args.branch}")

    if args.dry_run:
        print("🔍 Dry-run: будут выполнены следующие команды:")
        print(f"  git add -A")
        print(f"  git commit -m \"{args.message}\"")
        print(f"  git push origin {args.branch}")
        print("Изменённые файлы:")
        print(status)
        return

    # 3. Добавляем все изменения
    add_out = run_git(["add", "-A"])
    if add_out is None:
        sys.exit(1)

    # 4. Коммит
    commit_out = run_git(["commit", "-m", args.message])
    if commit_out is None:
        # Если ошибка "nothing to commit", это не страшно
        if "nothing to commit" in (run_git(["status"]) or ""):
            print("✅ Изменений для коммита нет.")
        else:
            sys.exit(1)
    else:
        print(f"✅ Коммит создан: \"{args.message}\"")

    # 5. Пуш
    print(f"🚀 Отправка изменений в origin/{args.branch}...")
    push_out = run_git(["push", "origin", args.branch])
    if push_out is None:
        print("❌ Не удалось выполнить push. Возможно, нет прав или нужен pull.")
        sys.exit(1)
    print("🎉 Готово! Изменения успешно отправлены на GitHub.")

if __name__ == "__main__":
    main()
