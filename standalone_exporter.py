#!/usr/bin/env python3
"""
Universal Project Dumper v4.5 — Interactive Menu Edition
========================================================
Запускай через F5 в VS Code — покажет меню.
Собирает ВСЕ файлы рядом и в подпапках. Ничего не пропускает из структуры.
"""

import os
import sys
import json
import base64
import hashlib
import platform
import mimetypes
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple

# Пытаемся импортировать colorama для цветов в Windows
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class _FakeColor:
        def __getattr__(self, name):
            return ""
    Fore = Style = _FakeColor()

# Увеличиваем лимит рекурсии для глубоких проектов
sys.setrecursionlimit(10000)

# ============ КОНФИГУРАЦИЯ ============
VERSION = "4.5-interactive"

# Директории, содержимое которых пропускаем в Smart режиме (только структура)
SMART_SKIP_DIRS: Set[str] = {
    '__pycache__', '.git', '.svn', '.hg', '.venv', 'venv',
    'node_modules', '.pytest_cache', '.idea', '.vscode',
    'dist', 'build', '.eggs', '.tox',
}

# Расширения, содержимое которых пропускаем в Smart режиме
SMART_SKIP_EXTS: Set[str] = {
    '.pkl', '.pickle', '.db', '.sqlite', '.sqlite3', '.whl',
    '.tar', '.gz', '.zip', '.rar', '.7z', '.exe', '.dll',
    '.so', '.dylib', '.bin', '.jpg', '.jpeg', '.png', '.gif',
    '.ico', '.bmp', '.svg', '.mp3', '.mp4', '.avi', '.mov',
    '.wav', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.pyd',
}

# Текстовые расширения (приоритет)
TEXT_EXTS: Set[str] = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.xml', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.txt', '.md', '.rst', '.log',
    '.sql', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.html', '.htm', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
    '.c', '.cpp', '.h', '.hpp', '.cs', '.java', '.kt', '.scala', '.go',
    '.rs', '.rb', '.php', '.pl', '.lua', '.r', '.m', '.swift', '.dart',
    '.erl', '.ex', '.exs', '.clj', '.cljs', '.hs', '.lhs', '.fs', '.fsx',
    '.ml', '.mli', '.v', '.cr', '.nim', '.pas', '.pp', '.dpr', '.dfm',
    '.graphql', '.prisma', '.proto', '.thrift', '.dockerfile', '.gitignore',
    '.gitattributes', '.editorconfig', '.env', '.envrc', '.htaccess', '.nginx',
    '.apache2', '.service', '.timer', '.socket', '.device', '.mount',
    '.automount', '.swap', '.target', '.path', '.slice', '.scope', '.patch',
    '.diff', '.lock', '.sum', '.mod', '.qss', '.bak', '.py.bak', '.json.bak',
}


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {title}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")


def print_success(msg: str):
    print(f"{Fore.GREEN}✅ {msg}{Style.RESET_ALL}")


def print_warning(msg: str):
    print(f"{Fore.YELLOW}⚠️  {msg}{Style.RESET_ALL}")


def print_error(msg: str):
    print(f"{Fore.RED}❌ {msg}{Style.RESET_ALL}")


def print_info(msg: str):
    print(f"{Fore.BLUE}ℹ️  {msg}{Style.RESET_ALL}")


def wait_key():
    input(f"\n{Fore.CYAN}Нажмите Enter для продолжения...{Style.RESET_ALL}")


class ProjectDumper:
    def __init__(
        self,
        project_root: Path,
        mode: str = "smart",
        max_file_size: int = 10 * 1024 * 1024,  # 10 MB по умолчанию
        pretty: bool = True,
        output_file: Optional[Path] = None,
    ):
        self.project_root = project_root.resolve()
        self.mode = mode  # 'smart', 'full', 'structure'
        self.max_file_size = max_file_size
        self.pretty = pretty
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if output_file:
            self.output_file = output_file.resolve()
        else:
            self.output_file = self.project_root / f"FULL_DUMP_{self.timestamp}.json"

        self.stats = {
            "total_files": 0,
            "total_dirs": 0,
            "text_files": 0,
            "binary_files": 0,
            "empty_files": 0,
            "skipped_content": 0,
            "errors": 0,
            "total_bytes": 0,
        }
        self.errors: List[str] = []
        self.files_data: Dict[str, Any] = {}
        self.structure_data: Dict[str, Any] = {}

    def _file_info(self, path: Path) -> Dict[str, Any]:
        try:
            st = path.stat()
            return {
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(st.st_ctime).isoformat(),
                "permissions": oct(st.st_mode)[-3:],
            }
        except Exception as e:
            return {"error": str(e), "size": 0}

    def _read_text(self, path: Path) -> Optional[str]:
        for enc in ('utf-8', 'latin-1', 'cp1251', 'cp1252', 'iso-8859-1'):
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
            except Exception:
                return None
        return None

    def _read_base64(self, path: Path) -> str:
        try:
            return base64.b64encode(path.read_bytes()).decode('ascii')
        except Exception as e:
            return f"[BASE64_ERROR: {e}]"

    def _should_skip_content(self, path: Path, size: int) -> Tuple[bool, str]:
        """В Smart режиме пропускаем содержимое бинарного мусора и огромных файлов."""
        if self.mode == "structure":
            return True, "structure-only"

        ext = path.suffix.lower()
        double_ext = "".join(path.suffixes).lower()

        if self.mode == "smart":
            if ext in SMART_SKIP_EXTS or double_ext in SMART_SKIP_EXTS:
                return True, f"binary ext {ext} (smart skip)"
            # Папки бэкапов/кэшей полностью пропускаем содержимое
            parts = {p.lower() for p in path.parts}
            if parts & {'__pycache__', '.git', 'node_modules', '.venv'}:
                return True, "inside skipped dir"

        if size > self.max_file_size:
            return True, f"file size {size:,} > limit {self.max_file_size:,}"

        return False, ""

    def _process_file(self, path: Path, rel_path: str) -> Dict[str, Any]:
        info = self._file_info(path)
        size = info.get("size", 0)
        ext = path.suffix.lower()

        entry: Dict[str, Any] = {
            "path": rel_path,
            "name": path.name,
            "extension": ext,
            "mime_type": mimetypes.guess_type(str(path))[0] or "unknown",
            "info": info,
        }

        if size == 0:
            entry["type"] = "empty"
            entry["content"] = ""
            self.stats["empty_files"] += 1
            return entry

        skip, reason = self._should_skip_content(path, size)
        if skip:
            entry["type"] = "skipped"
            entry["skip_reason"] = reason
            self.stats["skipped_content"] += 1
            return entry

        # Пробуем как текст
        is_text = (
            ext in TEXT_EXTS or
            not ext or
            (entry["mime_type"] and entry["mime_type"].startswith(('text/', 'application/json', 'application/xml')))
        )

        if is_text:
            text = self._read_text(path)
            if text is not None:
                entry["type"] = "text"
                entry["content"] = text
                entry["encoding"] = "utf-8"
                entry["lines"] = text.count('\n') + 1
                self.stats["text_files"] += 1
                return entry

        # Бинарник в base64
        entry["type"] = "binary"
        entry["encoding"] = "base64"
        entry["content"] = self._read_base64(path)
        try:
            entry["hash_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception as e:
            entry["hash_sha256"] = f"[error: {e}]"
        self.stats["binary_files"] += 1
        return entry

    def _scan_dir(self, current: Path, rel_prefix: str = "") -> Dict[str, Any]:
        node: Dict[str, Any] = {
            "type": "directory",
            "path": rel_prefix or ".",
            "files": {},
            "subdirectories": {},
        }

        try:
            entries = list(os.scandir(current))
        except (PermissionError, OSError) as e:
            self.errors.append(f"Access denied: {current} ({e})")
            node["error"] = str(e)
            return node

        files = [e for e in entries if e.is_file(follow_symlinks=False)]
        dirs = [e for e in entries if e.is_dir(follow_symlinks=False)]

        # Обрабатываем файлы
        for entry in sorted(files, key=lambda x: x.name):
            rel = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            try:
                data = self._process_file(Path(entry.path), rel)
                node["files"][entry.name] = {
                    "type": "file",
                    "size": data["info"].get("size", 0),
                }
                self.files_data[rel] = data
                self.stats["total_files"] += 1
                self.stats["total_bytes"] += data["info"].get("size", 0)

                # Прогресс каждые 50 файлов
                if self.stats["total_files"] % 50 == 0:
                    print(f"   {Fore.YELLOW}... обработано {self.stats['total_files']} файлов{Style.RESET_ALL}", end='\r')

            except Exception as e:
                self.errors.append(f"Error on {rel}: {e}")
                self.stats["errors"] += 1

        # Обрабатываем папки
        for entry in sorted(dirs, key=lambda x: x.name):
            name = entry.name
            rel = f"{rel_prefix}/{name}" if rel_prefix else name

            # В Smart режиме некоторые папки пропускаем рекурсивно
            if self.mode == "smart" and name in SMART_SKIP_DIRS:
                node["subdirectories"][name] = {
                    "type": "directory",
                    "path": rel,
                    "skipped": True,
                    "reason": "excluded by smart filter",
                }
                continue

            self.stats["total_dirs"] += 1
            node["subdirectories"][name] = self._scan_dir(Path(entry.path), rel)

        return node

    def validate(self) -> Tuple[bool, List[str]]:
        """Проверяем, что каждый файл из structure есть в files."""
        missing: List[str] = []

        def walk(node: Dict[str, Any], prefix: str = ""):
            for fname in node.get("files", {}):
                fpath = f"{prefix}/{fname}" if prefix else fname
                if fpath not in self.files_data:
                    missing.append(fpath)
            for dname, sub in node.get("subdirectories", {}).items():
                if sub.get("skipped"):
                    continue
                walk(sub, f"{prefix}/{dname}" if prefix else dname)

        walk(self.structure_data)
        return len(missing) == 0, missing

    def run(self) -> Optional[Path]:
        print_info(f"Сканирование: {self.project_root}")
        print_info(f"Режим: {self.mode} | Max size: {self.max_file_size:,} bytes")

        # Сканируем
        self.structure_data = self._scan_dir(self.project_root)

        # Собираем JSON
        dump = {
            "meta": {
                "version": VERSION,
                "timestamp": self.timestamp,
                "mode": self.mode,
                "project_root": str(self.project_root),
                "system": {
                    "os": platform.system(),
                    "python": platform.python_version(),
                    "machine": platform.machine(),
                }
            },
            "structure": self.structure_data,
            "files": self.files_data,
            "stats": self.stats,
            "errors": self.errors,
        }

        # Валидация
        print("\n🔍 Валидация целостности...")
        ok, missing = self.validate()
        if ok:
            print_success("Все файлы из структуры присутствуют в секции files")
            dump["validation"] = {"status": "OK"}
        else:
            print_error(f"Обнаружены пропуски: {len(missing)} файлов!")
            for m in missing[:10]:
                print(f"   - {m}")
            dump["validation"] = {
                "status": "INCOMPLETE",
                "missing_count": len(missing),
                "missing_sample": missing[:50],
            }

        # Запись
        print_info(f"Запись в {self.output_file} ...")
        try:
            if self.pretty:
                text = json.dumps(dump, ensure_ascii=False, indent=2, default=str)
            else:
                text = json.dumps(dump, ensure_ascii=False, default=str)

            self.output_file.write_text(text, encoding='utf-8')
        except Exception as e:
            print_error(f"Ошибка записи: {e}")
            # Fallback
            fb = self.project_root / f"FULL_DUMP_{self.timestamp}_fallback.json"
            fb.write_text(json.dumps(dump, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            print_info(f"Сохранён резервный файл: {fb}")
            return fb

        # Проверка записи
        try:
            written = self.output_file.read_text(encoding='utf-8')
            parsed = json.loads(written)
            assert "structure" in parsed and "files" in parsed
            print_success("Файл записан и проверен")
        except Exception as e:
            print_error(f"Файл записан, но повреждён: {e}")

        size_mb = self.output_file.stat().st_size / (1024 * 1024)
        print_success(f"Готово: {self.output_file.name} ({size_mb:.2f} MB)")
        print_info(f"Файлов: {self.stats['total_files']} | Папок: {self.stats['total_dirs']}")
        print_info(f"Текстовых: {self.stats['text_files']} | Бинарных: {self.stats['binary_files']} | Пропущено: {self.stats['skipped_content']}")
        if self.stats['errors']:
            print_warning(f"Ошибок при обработке: {self.stats['errors']}")

        if size_mb > 30:
            print_warning("Файл дампа >30 MB! При загрузке в чат может обрезаться.")
            print_info("Рекомендация: используй режим Smart или увеличь лимит чата.")

        return self.output_file


def find_project_root() -> Path:
    """Определяем корень проекта."""
    # Если рядом есть папка src — это корень
    cwd = Path.cwd()
    if (cwd / "src").exists():
        return cwd

    # Если скрипт лежит в корне
    script_dir = Path(__file__).parent.resolve()
    if (script_dir / "src").exists():
        return script_dir

    return cwd


def menu_smart():
    clear_screen()
    print_header("📦 SMART EXPORT")
    print("Собирает ВСЕ файлы проекта.\nБинарный мусор (кэши, .pkl, картинки) — в структуре, но без содержимого.\nИсходный код и конфиги — полностью.")
    root = find_project_root()
    print_info(f"Корень проекта: {root}")
    dumper = ProjectDumper(root, mode="smart", pretty=True)
    dumper.run()
    wait_key()


def menu_full():
    clear_screen()
    print_header("🔥 FULL EXPORT")
    print("Собирает ВСЕ файлы включая base64 содержимое бинарников.\nМожет занять много времени и места!")
    root = find_project_root()
    print_info(f"Корень проекта: {root}")
    try:
        limit = input(f"{Fore.YELLOW}Лимит размера файла (MB) [10]: {Style.RESET_ALL}").strip()
        limit_mb = int(limit) if limit else 10
    except ValueError:
        limit_mb = 10
    dumper = ProjectDumper(root, mode="full", max_file_size=limit_mb * 1024 * 1024, pretty=True)
    dumper.run()
    wait_key()


def menu_structure():
    clear_screen()
    print_header("🌳 STRUCTURE ONLY")
    print("Только дерево файлов и папок без содержимого.")
    root = find_project_root()
    dumper = ProjectDumper(root, mode="structure", pretty=True)
    dumper.run()
    wait_key()


def menu_custom():
    clear_screen()
    print_header("⚙️ CUSTOM EXPORT")
    root = find_project_root()
    path_input = input(f"Путь к проекту [{root}]: ").strip()
    if path_input:
        root = Path(path_input)

    print("\nРежимы:")
    print("  1 — smart (код + конфиги, бинарники без содержимого)")
    print("  2 — full (всё в base64)")
    print("  3 — structure (только дерево)")
    mode_map = {"1": "smart", "2": "full", "3": "structure"}
    choice = input("Выбор [1]: ").strip() or "1"
    mode = mode_map.get(choice, "smart")

    try:
        max_mb = int(input("Max размер файла (MB) [10]: ").strip() or "10")
    except ValueError:
        max_mb = 10

    pretty = input("Красивый формат с отступами? [Y/n]: ").strip().lower() != "n"

    dumper = ProjectDumper(root, mode=mode, max_file_size=max_mb*1024*1024, pretty=pretty)
    dumper.run()
    wait_key()


def menu_validate():
    clear_screen()
    print_header("🔍 VALIDATE LAST DUMP")
    root = find_project_root()
    dumps = sorted(root.glob("FULL_DUMP_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dumps:
        print_error("Дампы не найдены!")
        wait_key()
        return

    print_info(f"Последний дамп: {dumps[0].name}")
    try:
        data = json.loads(dumps[0].read_text(encoding='utf-8'))
        files_count = len(data.get("files", {}))
        struct_files = count_files_in_structure(data.get("structure", {}))
        print_info(f"Файлов в секции 'files': {files_count}")
        print_info(f"Файлов в 'structure': {struct_files}")
        if files_count == struct_files:
            print_success("Дамп целостный!")
        else:
            print_warning(f"Разница: {struct_files - files_count} файлов из структуры без содержимого")
    except Exception as e:
        print_error(f"Ошибка чтения дампа: {e}")
    wait_key()


def count_files_in_structure(node: Dict[str, Any]) -> int:
    count = len(node.get("files", {}))
    for sub in node.get("subdirectories", {}).values():
        if not sub.get("skipped"):
            count += count_files_in_structure(sub)
    return count


def menu_cleanup():
    clear_screen()
    print_header("🧹 CLEANUP OLD DUMPS")
    root = find_project_root()
    dumps = list(root.glob("FULL_DUMP_*.json"))
    if not dumps:
        print_info("Нет дампов для удаления")
        wait_key()
        return

    print_info(f"Найдено дампов: {len(dumps)}")
    for d in dumps:
        size = d.stat().st_size / (1024 * 1024)
        print(f"   {d.name} ({size:.1f} MB)")
    confirm = input(f"\n{Fore.RED}Удалить ВСЕ дампы? [y/N]: {Style.RESET_ALL}").strip().lower()
    if confirm == 'y':
        for d in dumps:
            d.unlink()
        print_success("Удалено!")
    else:
        print_info("Отменено")
    wait_key()


def main_menu():
    while True:
        clear_screen()
        root = find_project_root()
        print_header(f"Universal Project Dumper v{VERSION}")
        print(f"  Корень проекта: {Fore.YELLOW}{root}{Style.RESET_ALL}\n")
        print(f"  {Fore.GREEN}[1]{Style.RESET_ALL} 📦  Smart Export  (рекомендуется)")
        print(f"  {Fore.GREEN}[2]{Style.RESET_ALL} 🔥  Full Export   (всё в base64, осторожно)")
        print(f"  {Fore.GREEN}[3]{Style.RESET_ALL} 🌳  Structure Only")
        print(f"  {Fore.GREEN}[4]{Style.RESET_ALL} ⚙️  Custom Export")
        print(f"  {Fore.YELLOW}[5]{Style.RESET_ALL} 🔍  Validate Last Dump")
        print(f"  {Fore.YELLOW}[6]{Style.RESET_ALL} 🧹  Cleanup Old Dumps")
        print(f"  {Fore.RED}[0]{Style.RESET_ALL} ❌  Exit\n")

        choice = input(f"{Fore.CYAN}Выберите пункт: {Style.RESET_ALL}").strip()

        if choice == "1":
            menu_smart()
        elif choice == "2":
            menu_full()
        elif choice == "3":
            menu_structure()
        elif choice == "4":
            menu_custom()
        elif choice == "5":
            menu_validate()
        elif choice == "6":
            menu_cleanup()
        elif choice == "0":
            print_info("Выход...")
            break
        else:
            print_error("Неверный выбор!")
            wait_key()


def cli_main():
    parser = argparse.ArgumentParser(description="Universal Project Dumper v4.5")
    parser.add_argument("path", nargs="?", help="Путь к проекту")
    parser.add_argument("--mode", choices=["smart", "full", "structure"], default="smart")
    parser.add_argument("--max-size", type=int, default=10, help="Max file size in MB")
    parser.add_argument("--compact", action="store_true", help="Minify JSON")
    parser.add_argument("--output", type=str, help="Output filename")
    args = parser.parse_args()

    root = Path(args.path).resolve() if args.path else find_project_root()
    out = Path(args.output) if args.output else None
    dumper = ProjectDumper(
        root,
        mode=args.mode,
        max_file_size=args.max_size * 1024 * 1024,
        pretty=not args.compact,
        output_file=out,
    )
    dumper.run()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_main()
    else:
        main_menu()
