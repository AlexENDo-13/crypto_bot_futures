#!/usr/bin/env python3
"""
Автоматическое исправление position_side в main_window.py
и опциональный пуш на GitHub.
Запуск:
    python fix_and_push_v2.py            # только исправить
    python fix_and_push_v2.py --push     # исправить + коммит + пуш
"""

import re
import sys
from pathlib import Path

def fix_main_window():
    """Заменяет вызовы close_position_async с pos.side на правильное преобразование."""
    file = Path("src/ui/main_window.py")
    if not file.exists():
        print("❌ Файл main_window.py не найден в src/ui/")
        sys.exit(1)

    content = file.read_text(encoding="utf-8")

    # Паттерн для вызова close_position_async с position_side=pos.side
    pattern = re.compile(
        r'(\.close_position_async\()\s*symbol\s*=\s*sym,\s*position_side\s*=\s*pos\.side,\s*quantity\s*=\s*pos\.quantity',
        re.DOTALL
    )

    # Подготовим замену с преобразованием
    replacement = (
        r'\1symbol=sym,\n'
        r'                    position_side=("LONG" if pos.side == OrderSide.BUY else "SHORT"),\n'
        r'                    quantity=pos.quantity'
    )

    new_content, count = pattern.subn(replacement, content)

    if count == 0:
        # Попробуем другой вариант – если написано side=pos.side вместо position_side
        pattern2 = re.compile(
            r'(\.close_position_async\()\s*symbol\s*=\s*sym,\s*side\s*=\s*pos\.side,\s*quantity\s*=\s*pos\.quantity',
            re.DOTALL
        )
        replacement2 = replacement  # та же замена, ведь аргумент всё равно будет position_side
        new_content, count = pattern2.subn(replacement2, content)

    if count == 0:
        print("ℹ️  Вызовы close_position_async с pos.side не найдены в main_window.py.")
        return False

    # Убедимся, что есть импорт OrderSide (если его нет, добавим)
    if "from src.core.trading.position import OrderSide" not in new_content:
        # Добавим импорт после первого import
        new_content = re.sub(
            r'(import [^\n]*\n)',
            r'\1from src.core.trading.position import OrderSide\n',
            new_content, count=1
        )

    file.write_text(new_content, encoding="utf-8")
    print(f"✅ Исправлено {count} вызовов в main_window.py")
    return True

def push_to_github(message="Fix position_side in emergency close"):
    """Пуш в GitHub через git (без сторонних библиотек)."""
    import subprocess
    try:
        subprocess.run(["git", "add", "-A"], cwd=".", check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=".", check=False)
        subprocess.run(["git", "push", "origin", "main"], cwd=".", check=True)
        print("🚀 Изменения отправлены на GitHub")
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="Запушить исправления на GitHub")
    parser.add_argument("-m", "--message", default="Fix position_side in emergency close",
                        help="Сообщение коммита")
    args = parser.parse_args()

    print("🔧 Исправление close_position_async в main_window.py...")
    if fix_main_window():
        if args.push:
            push_to_github(args.message)
    else:
        print("Ничего не изменено.")
