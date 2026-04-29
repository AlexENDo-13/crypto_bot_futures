#!/usr/bin/env python3
"""
Исправление ошибки side → position_side в вызовах close_position_async.
Улучшенный поиск: учитывает вызовы от объектов, многострочность.
"""

import re
from pathlib import Path

def fix_side_arg(root_dir="."):
    changed = []
    # Ищем: всё что угодно, потом ".close_position_async(" или просто "close_position_async(",
    # дальше любые символы (в том числе переносы строк) до первой "side" с необязательными пробелами и "=".
    # Заменяем "side" на "position_side" внутри этих вызовов.
    pattern = re.compile(
        r'(\.?\s*close_position_async\s*\((?:(?!\bside\s*=).)*?)\bside\s*(=)',
        re.DOTALL
    )
    for py_file in Path(root_dir).rglob("*.py"):
        if any(p.startswith('.') or p in ('venv','env','__pycache__','.git') for p in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except:
            continue
        if 'close_position_async' not in content:
            continue
        new_content, n = pattern.subn(r'\1position_side\2', content)
        if n > 0:
            py_file.write_text(new_content, encoding="utf-8")
            changed.append((str(py_file), n))
            print(f"  ✅ {py_file}: {n} замен(ы)")
    return changed

if __name__ == "__main__":
    print("🔍 Расширенный поиск ошибки position_side= в close_position_async...")
    changes = fix_side_arg()
    if not changes:
        print("ℹ️  Файлы не найдены. Проверьте вручную вызовы вида: await obj.close_position_async(symbol, position_side='...')")
    else:
        print(f"\n🎯 Исправлено файлов: {len(changes)}")
