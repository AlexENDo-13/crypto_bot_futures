#!/usr/bin/env python3
"""
SafePatcher v3.4 — надёжное применение unified diff патчей с валидацией + автоочистка.
Новое: поддержка прямой замены файла через --replace-file.
"""
import sys
import re
import ast
import shutil
import tempfile
import hashlib
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Set
from dataclasses import dataclass
from enum import Enum

# ---------- Цвета ----------
class Colors:
    OK = '\033[92m'
    WARN = '\033[93m'
    ERR = '\033[91m'
    INFO = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    CYAN = '\033[96m'

    @classmethod
    def green(cls, s): return f"{cls.OK}{s}{cls.RESET}"
    @classmethod
    def yellow(cls, s): return f"{cls.WARN}{s}{cls.RESET}"
    @classmethod
    def red(cls, s): return f"{cls.ERR}{s}{cls.RESET}"
    @classmethod
    def blue(cls, s): return f"{cls.INFO}{s}{cls.RESET}"
    @classmethod
    def cyan(cls, s): return f"{cls.CYAN}{s}{cls.RESET}"
    @classmethod
    def bold(cls, s): return f"{cls.BOLD}{s}{cls.RESET}"

# ---------- Модели данных ----------
class HunkStatus(Enum):
    OK = "ok"
    CONTEXT_MISMATCH = "context_mismatch"
    OFFSET_APPLIED = "offset_applied"
    FAILED = "failed"

@dataclass
class HunkLine:
    tag: str  # ' ' (context), '+' (add), '-' (remove)
    content: str
    lineno: Optional[int] = None

@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[HunkLine]
    
    def old_lines(self) -> List[str]:
        return [l.content for l in self.lines if l.tag in (' ', '-')]

    def new_lines(self) -> List[str]:
        return [l.content for l in self.lines if l.tag in (' ', '+')]

@dataclass
class FilePatch:
    old_path: str
    new_path: str
    hunks: List[Hunk]
    is_new_file: bool = False
    is_deleted: bool = False

# ---------- Парсер unified diff ----------
class DiffParser:
    @staticmethod
    def parse(diff_text: str) -> List[FilePatch]:
        patches = []
        diff_text = diff_text.replace('\r\n', '\n')
        
        file_blocks = re.split(r'\ndiff --git ', diff_text)
        if not diff_text.startswith('diff --git '):
            file_blocks = file_blocks[1:]
        
        for block in file_blocks:
            block = 'diff --git ' + block
            patch = DiffParser._parse_file_block(block)
            if patch:
                patches.append(patch)
        
        if not patches:
            patches = DiffParser._parse_classic(diff_text)
            
        return patches
    
    @staticmethod
    def _parse_file_block(block: str) -> Optional[FilePatch]:
        lines = block.split('\n')
        if not lines:
            return None
            
        old_path, new_path = "", ""
        for line in lines[:5]:
            m = re.match(r'^diff --git a/(.*?) b/(.*?)$', line)
            if m:
                old_path, new_path = m.group(1), m.group(2)
                break
        
        if not old_path and not new_path:
            return None
            
        is_new = any('new file mode' in l for l in lines[:10])
        is_deleted = any('deleted file mode' in l for l in lines[:10])
        
        hunks = []
        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.match(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
            if m:
                old_start = int(m.group(1))
                old_count = int(m.group(2)) if m.group(2) else 1
                new_start = int(m.group(3))
                new_count = int(m.group(4)) if m.group(4) else 1
                
                hunk_lines = []
                i += 1
                while i < len(lines):
                    if i >= len(lines):
                        break
                    l = lines[i]
                    if l.startswith('@@') or l.startswith('diff --git'):
                        break
                    if l.startswith('\\'):
                        i += 1
                        continue
                    if len(l) > 0 and l[0] in (' ', '+', '-'):
                        tag = l[0]
                        content = l[1:]
                        hunk_lines.append(HunkLine(tag=tag, content=content))
                    elif l.strip() == '':
                        hunk_lines.append(HunkLine(tag=' ', content=''))
                    i += 1
                
                hunks.append(Hunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=hunk_lines
                ))
                continue
            i += 1
        
        if not hunks and not is_new:
            return None
            
        return FilePatch(
            old_path=old_path or new_path,
            new_path=new_path or old_path,
            hunks=hunks,
            is_new_file=is_new,
            is_deleted=is_deleted
        )
    
    @staticmethod
    def _parse_classic(diff_text: str) -> List[FilePatch]:
        patches = []
        lines = diff_text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('--- '):
                old_path = line[4:].split('\t')[0]
                if i + 1 < len(lines) and lines[i+1].startswith('+++ '):
                    new_path = lines[i+1][4:].split('\t')[0]
                    i += 2
                    hunks = []
                    while i < len(lines):
                        if lines[i].startswith('--- '):
                            break
                        m = re.match(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', lines[i])
                        if m:
                            old_start = int(m.group(1))
                            old_count = int(m.group(2)) if m.group(2) else 1
                            new_start = int(m.group(3))
                            new_count = int(m.group(4)) if m.group(4) else 1
                            hunk_lines = []
                            i += 1
                            while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('--- '):
                                l = lines[i]
                                if len(l) > 0 and l[0] in (' ', '+', '-'):
                                    hunk_lines.append(HunkLine(tag=l[0], content=l[1:]))
                                i += 1
                            hunks.append(Hunk(old_start, old_count, new_start, new_count, hunk_lines))
                        else:
                            i += 1
                    if hunks:
                        patches.append(FilePatch(old_path, new_path, hunks))
                else:
                    i += 1
            else:
                i += 1
        return patches

# ---------- Валидатор и применялка ----------
class PatchApplier:
    def __init__(self, logger_func=print, strict: bool = False, fuzzy_radius: int = 20, force: bool = False):
        self.log = logger_func
        self.strict = strict
        self.fuzzy_radius = fuzzy_radius
        self.force = force
        self.warnings: List[str] = []
        self.stats = {"hunks_ok": 0, "hunks_offset": 0, "hunks_failed": 0}
    
    def apply_file_patch(self, target_file: Path, patch: FilePatch, dry_run: bool = False) -> Tuple[bool, List[str]]:
        if patch.is_new_file:
            if not dry_run:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                new_content = []
                for hunk in patch.hunks:
                    new_content.extend(hunk.new_lines())
                target_file.write_text('\n'.join(new_content) + '\n', encoding='utf-8')
            return True, []
        
        if patch.is_deleted:
            if not dry_run:
                target_file.unlink(missing_ok=True)
            return True, []
        
        if not target_file.exists():
            return False, [f"Файл {patch.new_path} не найден"]
        
        original_lines = target_file.read_text(encoding='utf-8').split('\n')
        if original_lines and original_lines[-1] == '':
            original_lines = original_lines[:-1]
        
        result_lines = original_lines.copy()
        errors = []
        
        for hunk in reversed(patch.hunks):
            success, offset, err = self._apply_hunk(result_lines, hunk, patch.new_path)
            if not success:
                errors.append(f"Hunk @@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@: {err}")
                self.stats["hunks_failed"] += 1
            else:
                if offset != 0:
                    self.stats["hunks_offset"] += 1
                    self.warnings.append(f"Offset {offset:+d} для {patch.new_path} (hunk @@ -{hunk.old_start}... @@)")
                else:
                    self.stats["hunks_ok"] += 1
        
        if errors:
            return False, errors
        
        if not dry_run:
            new_content = '\n'.join(result_lines)
            if target_file.suffix == '.py':
                try:
                    ast.parse(new_content)
                except SyntaxError as e:
                    return False, [f"Синтаксическая ошибка после патча: строка {e.lineno}: {e.msg}"]
            
            target_file.write_text(new_content + '\n', encoding='utf-8')
        
        return True, []
    
    def _apply_hunk(self, file_lines: List[str], hunk: Hunk, filename: str) -> Tuple[bool, int, str]:
        old_lines = hunk.old_lines()
        if not old_lines:
            insert_pos = min(hunk.new_start - 1, len(file_lines))
            new_only = [l.content for l in hunk.lines if l.tag == '+']
            for i, line in enumerate(new_only):
                file_lines.insert(insert_pos + i, line)
            return True, 0, ""
        
        best_offset = None
        best_score = -1
        
        max_offset = self.fuzzy_radius if not self.strict else 0
        search_start = max(0, hunk.old_start - 1 - max_offset)
        search_end = min(len(file_lines), hunk.old_start - 1 + max_offset + len(old_lines) + 2)
        
        for offset in range(search_start, search_end - len(old_lines) + 1):
            score = self._match_score(file_lines, offset, old_lines)
            if score > best_score:
                best_score = score
                best_offset = offset
        
        if self.strict:
            required_score = len(old_lines)
        elif self.force:
            required_score = max(1, int(len(old_lines) * 0.5))
        else:
            required_score = int(len(old_lines) * 0.8)
        
        if best_score < required_score:
            if self.force:
                self.warnings.append(f"Принудительное применение с низким совпадением ({best_score}/{len(old_lines)}) для {filename}")
                best_offset = max(0, min(len(file_lines) - len(old_lines), hunk.old_start - 1))
            else:
                return False, 0, f"Контекст не найден (лучшее совпадение: {best_score}/{len(old_lines)} строк)"
        
        actual_offset = best_offset - (hunk.old_start - 1)
        
        new_lines = []
        old_idx = best_offset
        
        for line in hunk.lines:
            if line.tag == ' ':
                if old_idx < len(file_lines) and file_lines[old_idx] == line.content:
                    new_lines.append(line.content)
                    old_idx += 1
                elif self.force:
                    new_lines.append(line.content)
                    self.warnings.append(f"Контекст не совпадает на строке {old_idx+1} в {filename}, игнорируем")
                    old_idx += 1
                else:
                    return False, 0, f"Контекст не совпадает на строке {old_idx + 1}"
            elif line.tag == '-':
                if old_idx < len(file_lines) and file_lines[old_idx] == line.content:
                    old_idx += 1
                elif self.force:
                    self.warnings.append(f"Строка для удаления не найдена в {filename}: '{line.content[:50]}', пропускаем")
                    old_idx += 1
                else:
                    return False, 0, f"Строка для удаления не найдена: '{line.content[:50]}'"
            elif line.tag == '+':
                new_lines.append(line.content)
        
        end_remove = best_offset + len([l for l in hunk.lines if l.tag in (' ', '-')])
        del file_lines[best_offset:end_remove]
        for i, nl in enumerate(new_lines):
            file_lines.insert(best_offset + i, nl)
        
        return True, actual_offset, ""
    
    def _match_score(self, file_lines: List[str], offset: int, old_lines: List[str]) -> int:
        score = 0
        for i, expected in enumerate(old_lines):
            if offset + i < len(file_lines):
                actual = file_lines[offset + i]
                if actual == expected:
                    score += 1
                elif actual.strip() == expected.strip():
                    score += 0.5
        return int(score)

# ---------- Основная логика ----------
def find_patch_files(root: Path) -> List[Path]:
    return sorted(
        [p for p in root.glob('*.patch')] + [p for p in root.glob('*.diff')],
        key=lambda x: x.stat().st_mtime, reverse=True
    )

def select_patch_file(root: Path) -> Optional[Path]:
    files = find_patch_files(root)
    if not files:
        print(Colors.yellow("Файлы .patch не найдены."))
        return None
    print(Colors.cyan("\nДоступные .patch файлы:"))
    for i, f in enumerate(files, 1):
        print(f"  {i}. {f.name} ({f.stat().st_size} bytes)")
    try:
        choice = input(Colors.yellow("Выберите номер: ")).strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                return files[idx]
    except (EOFError, KeyboardInterrupt):
        pass
    return None

def check_syntax(file_path: Path) -> Optional[str]:
    if file_path.suffix != '.py':
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return None
    except SyntaxError as e:
        return f"Строка {e.lineno}: {e.msg}"
    except Exception as e:
        return str(e)

def apply_patch_file(root: Path, patch_path: Path, dry_run: bool = False, 
                     strict: bool = False, all_or_nothing: bool = False,
                     fuzzy_radius: int = 20, force: bool = False) -> Dict[str, any]:
    with open(patch_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    patches = DiffParser.parse(content)
    if not patches:
        print(Colors.red(f"❌ Не удалось распарсить патч {patch_path.name}"))
        return {"success": 0, "errors": 1, "details": []}
    
    applier = PatchApplier(strict=strict, fuzzy_radius=fuzzy_radius, force=force)
    results = []
    total_success = 0
    total_errors = 0
    
    backups = {}
    
    print(Colors.blue(f"\n{'='*60}"))
    print(Colors.bold(f"  Патч: {patch_path.name}"))
    print(Colors.bold(f"  Режим: {'DRY-RUN (проверка)' if dry_run else 'ПРИМЕНЕНИЕ'}"))
    if strict:
        print(Colors.yellow("  Режим STRICT: только точное совпадение контекста"))
    if force:
        print(Colors.yellow("  Режим FORCE: применять даже при несовпадении контекста (с осторожностью)"))
    if all_or_nothing:
        print(Colors.yellow("  Режим ALL-OR-NOTHING: откат всех файлов при ошибке"))
    print(Colors.blue(f"{'='*60}\n"))
    
    if not dry_run and all_or_nothing:
        for patch in patches:
            if patch.is_new_file or patch.is_deleted:
                continue
            target_file = root / patch.new_path
            if target_file.exists():
                backup = target_file.with_suffix(target_file.suffix + '.bak')
                shutil.copy2(target_file, backup)
                backups[target_file] = backup
    
    for patch in patches:
        target_file = root / patch.new_path
        
        if patch.is_new_file:
            print(Colors.cyan(f"   📄 Новый файл: {patch.new_path}"))
        elif not target_file.exists():
            print(Colors.red(f"   ❌ Файл {patch.new_path} не найден"))
            total_errors += 1
            if all_or_nothing:
                break
            continue
        else:
            print(Colors.cyan(f"   📄 Обработка {patch.new_path}..."), end=' ')
        
        if not dry_run and target_file.exists() and target_file not in backups:
            backup = target_file.with_suffix(target_file.suffix + '.bak')
            shutil.copy2(target_file, backup)
            backups[target_file] = backup
        
        success, errors = applier.apply_file_patch(target_file, patch, dry_run=dry_run)
        
        if success:
            if not dry_run:
                syntax_err = check_syntax(target_file) if target_file.exists() else None
                if syntax_err:
                    if target_file in backups:
                        shutil.copy2(backups[target_file], target_file)
                    print(Colors.red(f"❌ Синтаксическая ошибка: {syntax_err}"))
                    total_errors += 1
                    results.append({"file": patch.new_path, "status": "rollback", "error": syntax_err})
                    if all_or_nothing:
                        break
                    continue
            
            status = "✅ OK (dry-run)" if dry_run else "✅ OK"
            print(Colors.green(status))
            total_success += 1
            results.append({"file": patch.new_path, "status": "ok"})
        else:
            if not dry_run and target_file in backups:
                shutil.copy2(backups[target_file], target_file)
            err_msg = "; ".join(errors)
            print(Colors.red(f"❌ {err_msg}"))
            total_errors += 1
            results.append({"file": patch.new_path, "status": "failed", "error": err_msg})
            if all_or_nothing:
                break
    
    if all_or_nothing and total_errors > 0:
        print(Colors.yellow("\n🔄 Откат всех изменений (режим all-or-nothing)..."))
        for target_file, backup in backups.items():
            if backup.exists() and target_file.exists():
                shutil.copy2(backup, target_file)
                print(f"   ↩️ {target_file.relative_to(root)} восстановлен")
        for backup in backups.values():
            backup.unlink(missing_ok=True)
        backups.clear()
    
    print(Colors.blue(f"\n{'='*60}"))
    print(Colors.bold("  Результат:"))
    print(f"  ✅ Успешно: {total_success}")
    print(f"  ❌ Ошибок: {total_errors}")
    if applier.warnings:
        print(Colors.yellow(f"  ⚠️ Предупреждения ({len(applier.warnings)}):"))
        for w in applier.warnings[:5]:
            print(f"     • {w}")
    print(Colors.blue(f"{'='*60}"))
    
    return {
        "success": total_success,
        "errors": total_errors,
        "warnings": applier.warnings,
        "details": results,
        "dry_run": dry_run,
        "patch_path": patch_path
    }

def replace_file(root: Path, file_path: str, new_content: str, dry_run: bool = False):
    """Заменяет файл целиком новым содержимым (с бэкапом)."""
    target = root / file_path
    if not target.exists() and not dry_run:
        print(Colors.yellow(f"Файл {file_path} не существует, будет создан."))
    if not dry_run:
        backup = target.with_suffix(target.suffix + '.bak')
        if target.exists():
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding='utf-8')
        # Проверка синтаксиса
        if target.suffix == '.py':
            err = check_syntax(target)
            if err:
                print(Colors.red(f"❌ Синтаксическая ошибка в {file_path}: {err}"))
                if target.exists():
                    shutil.copy2(backup, target)
                return False
        print(Colors.green(f"✅ Файл {file_path} заменён (бэкап: {backup.name})"))
    else:
        print(Colors.cyan(f"📄 [DRY-RUN] Будет заменён: {file_path}"))
    return True

def rollback_last(root: Path):
    bak_files = list(root.rglob('*.bak'))
    if not bak_files:
        print(Colors.yellow("Нет файлов .bak для отката."))
        return
    print(Colors.blue("\n🔄 Восстановление из .bak..."))
    restored = 0
    for bak in bak_files:
        orig = bak.with_suffix('')
        if orig.exists():
            shutil.copy2(bak, orig)
            print(f"   ✅ {orig.relative_to(root)} восстановлен.")
            restored += 1
    if restored == 0:
        print(Colors.yellow("   Нет файлов для восстановления."))
    else:
        print(Colors.green(f"Откат завершён. Восстановлено {restored} файлов."))

def check_syntax_project(root: Path):
    errors = 0
    src_dir = root / 'src'
    if not src_dir.exists():
        print(Colors.red("❌ Папка src/ не найдена."))
        return
    for py_file in src_dir.rglob('*.py'):
        err = check_syntax(py_file)
        if err:
            print(Colors.red(f"   ❌ {py_file.relative_to(root)}: {err}"))
            errors += 1
    if errors == 0:
        print(Colors.green("   ✅ Все файлы валидны."))
    else:
        print(Colors.red(f"\n❌ Найдено ошибок: {errors}"))

def cleanup_patch(patch_path: Path, root: Path):
    try:
        ans = input(Colors.yellow("   Удалить файл патча? [y/N]: ")).strip().lower()
        if ans in ('y', 'yes', 'да'):
            patch_path.write_text("", encoding='utf-8')
            print(Colors.green(f"   🧹 Файл {patch_path.name} очищен"))
            return True
        else:
            ans2 = input(Colors.yellow("   Переместить в data/patches_applied/? [y/N]: ")).strip().lower()
            if ans2 in ('y', 'yes', 'да'):
                dest = root / "data" / "patches_applied" / patch_path.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(patch_path), str(dest))
                print(Colors.green(f"   📁 Перемещён в {dest.relative_to(root)}"))
                return True
    except (EOFError, KeyboardInterrupt):
        pass
    return False

def show_menu():
    print(Colors.blue("\n" + "=" * 60))
    print(Colors.bold("   SafePatcher v3.4 — МЕНЮ"))
    print(Colors.blue("=" * 60))
    print("""
   [1] 📋 Показать доступные .patch файлы
   [2] 🔍 Проверить патч (dry-run)
   [3] 🚀 Применить патч (с бэкапом и валидацией)
   [4] 📄 Проверить синтаксис проекта
   [5] 🔙 Откат последнего изменения (из .bak)
   [6] 📝 Заменить файл целиком (из файла .new)
   [0] ❌ Выход
    """)

def main():
    parser = argparse.ArgumentParser(description="SafePatcher — безопасное применение патчей")
    parser.add_argument('--apply', type=str, help="Применить указанный файл патча")
    parser.add_argument('--dry-run', action='store_true', help="Проверить патч без внесения изменений")
    parser.add_argument('--strict', action='store_true', help="Требовать точного совпадения контекста (без fuzzy)")
    parser.add_argument('--all-or-nothing', action='store_true', help="Откатить все файлы, если хотя бы один не применился")
    parser.add_argument('--fuzzy-radius', type=int, default=20, help="Радиус поиска для fuzzy matching (по умолчанию 20)")
    parser.add_argument('--force', action='store_true', help="Применять патч даже при несовпадении контекста (опасно!)")
    parser.add_argument('--rollback', action='store_true', help="Откатить последние изменения (из .bak файлов)")
    parser.add_argument('--check', action='store_true', help="Проверить синтаксис всех .py файлов в src/")
    parser.add_argument('--replace-file', nargs=2, metavar=('FILE_PATH', 'NEW_CONTENT_FILE'),
                        help="Заменить файл целиком содержимым из указанного файла")
    parser.add_argument('--interactive', '-i', action='store_true', help="Запустить в интерактивном режиме")
    parser.add_argument('--clean', action='store_true', help="Очистить файл патча после успешного применения (без запроса)")
    
    args = parser.parse_args()
    
    root = Path(__file__).parent.resolve()
    if not (root / 'src').exists():
        print(Colors.red("❌ Папка src/ не найдена. Запустите патчер из корня проекта."))
        sys.exit(1)
    
    if args.replace_file:
        file_path, new_file = args.replace_file
        try:
            new_content = Path(new_file).read_text(encoding='utf-8')
        except Exception as e:
            print(Colors.red(f"Ошибка чтения файла с новым содержимым: {e}"))
            sys.exit(1)
        success = replace_file(root, file_path, new_content, dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    
    if args.apply:
        patch_path = Path(args.apply)
        if not patch_path.exists():
            print(Colors.red(f"Файл {patch_path} не найден"))
            sys.exit(1)
        result = apply_patch_file(root, patch_path, dry_run=args.dry_run,
                                  strict=args.strict, all_or_nothing=args.all_or_nothing,
                                  fuzzy_radius=args.fuzzy_radius, force=args.force)
        if not args.dry_run and result["errors"] == 0:
            if args.clean:
                patch_path.write_text("", encoding='utf-8')
                print(Colors.green(f"🧹 Файл патча {patch_path.name} очищен"))
            else:
                cleanup_patch(patch_path, root)
        sys.exit(0 if result["errors"] == 0 else 1)
    elif args.rollback:
        rollback_last(root)
        sys.exit(0)
    elif args.check:
        check_syntax_project(root)
        sys.exit(0)
    elif args.interactive:
        pass
    elif len(sys.argv) > 1:
        parser.print_help()
        sys.exit(0)
    
    while True:
        show_menu()
        try:
            choice = input(Colors.yellow("   Выберите режим [0-6]: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Выход")
            break

        if choice == '0':
            print("👋 До свидания")
            break
        elif choice == '1':
            files = find_patch_files(root)
            if files:
                print(Colors.cyan("\nДоступные .patch файлы:"))
                for i, f in enumerate(files, 1):
                    print(f"  {i}. {f.name}")
            else:
                print(Colors.yellow("Файлы не найдены."))
        elif choice == '2':
            patch_file = select_patch_file(root)
            if patch_file:
                apply_patch_file(root, patch_file, dry_run=True)
        elif choice == '3':
            patch_file = select_patch_file(root)
            if patch_file:
                result = apply_patch_file(root, patch_file, dry_run=False)
                if result["errors"] > 0 and result["success"] == 0:
                    print(Colors.red("\n💥 Патч полностью провалился. Все файлы восстановлены из бэкапов."))
                elif result["errors"] > 0:
                    print(Colors.yellow("\n⚠️ Патч применён частично. Некоторые файлы откачены."))
                else:
                    cleanup_patch(patch_file, root)
        elif choice == '4':
            check_syntax_project(root)
        elif choice == '5':
            rollback_last(root)
        elif choice == '6':
            file_path = input("Введите путь к файлу относительно корня (например, src/utils/api_client.py): ").strip()
            new_file_path = input("Введите путь к файлу с новым содержимым: ").strip()
            if not file_path or not new_file_path:
                print(Colors.red("Путь не может быть пустым."))
                continue
            try:
                new_content = Path(new_file_path).read_text(encoding='utf-8')
            except Exception as e:
                print(Colors.red(f"Ошибка чтения: {e}"))
                continue
            replace_file(root, file_path, new_content)
        else:
            print(Colors.red("Неверный выбор."))
        print()

if __name__ == "__main__":
    main()
