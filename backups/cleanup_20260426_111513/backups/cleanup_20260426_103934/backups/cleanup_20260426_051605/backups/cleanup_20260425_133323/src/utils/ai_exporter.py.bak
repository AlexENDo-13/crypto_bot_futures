"""
AI Exporter – создание полного отчёта о состоянии бота для анализа ИИ.
Экспортирует: конфигурацию, веса стратегий, аналитику сделок, системную информацию,
логи, исходный код (с деталями отступов) и граф зависимостей.
"""
import json
import os
import ast
import hashlib
import platform
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

import psutil

from src.core.logger import BotLogger


class AIExporter:
    # Исключаем только служебные папки, которые не являются исходниками
    EXCLUDE_DIRS = {
        "__pycache__",
        ".git",
        ".idea",
        ".vscode",
        "venv", "env", ".venv", ".env",
        "build", "dist",
        "data/ai_exports",  # не рекурсивно
        "node_modules",
    }

    def __init__(
        self,
        config: Dict,
        weights: Dict,
        engine_state: Optional[Dict] = None,
        logger: Optional[BotLogger] = None,
    ):
        self.config = self._mask_sensitive(config.copy())
        self.weights = weights
        self.engine_state = engine_state
        self.logger = logger or BotLogger(level="INFO")

        self.project_root = Path(__file__).parent.parent.parent.resolve()
        self.export_dir = self.project_root / "data" / "ai_exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.previous_export = None

    def _mask_sensitive(self, cfg: Dict) -> Dict:
        sensitive_keys = [
            "api_key", "api_secret",
            "telegram_bot_token", "telegram_chat_id",
            "pushover_user_key", "pushover_api_token",
            "discord_webhook_url",
        ]
        for key in sensitive_keys:
            if key in cfg and cfg[key]:
                cfg[key] = "***MASKED***"
        return cfg

    def _file_hash(self, content: str) -> str:
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]

    def _minify_python(self, content: str) -> str:
        try:
            tree = ast.parse(content)
            lines = content.splitlines(keepends=True)
            docstring_lines = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                    if (node.body and isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant) and
                        isinstance(node.body[0].value.value, str)):
                        start = node.body[0].lineno - 1
                        end = getattr(node.body[0], 'end_lineno', start + 1)
                        for i in range(start, end):
                            docstring_lines.add(i)
            result = []
            prev_empty = False
            for i, line in enumerate(lines):
                if i in docstring_lines:
                    continue
                stripped = line.strip()
                is_empty = not stripped
                if is_empty and prev_empty:
                    continue
                result.append(line)
                prev_empty = is_empty
            return ''.join(result)
        except:
            return content

    def _collect_system_info(self) -> Dict:
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_freq = psutil.cpu_freq()
            return {
                "os": platform.system(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": sys.version,
                "hostname": platform.node(),
                "cpu_count": os.cpu_count(),
                "cpu_freq_current": cpu_freq.current if cpu_freq else None,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
            }
        except Exception as e:
            return {"error": f"Failed to collect system info: {e}"}

    def _collect_package_versions(self) -> Dict:
        packages = [
            "ccxt", "pandas", "numpy", "PyQt5", "requests", "ta",
            "deap", "schedule", "colorama", "cryptography", "aiohttp",
            "psutil", "matplotlib", "sklearn", "xgboost",
        ]
        versions = {}
        for pkg in packages:
            try:
                module = __import__(pkg.replace("-", "_"))
                versions[pkg] = getattr(module, "__version__", "unknown")
            except ImportError:
                versions[pkg] = "not installed"
        return versions

    def _collect_logs(self, lines: int = 300) -> str:
        log_dir = self.project_root / "data" / "logs"
        if not log_dir.exists():
            return "Логи не найдены"
        log_files = sorted(log_dir.glob("*_bot.log"), reverse=True)
        if not log_files:
            return "Файлы логов не найдены"
        try:
            with open(log_files[0], 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except IOError:
            return "Ошибка чтения логов"

    def _collect_trade_stats(self) -> Dict:
        try:
            from src.utils.sqlite_history import SQLiteTradeHistory
            db = SQLiteTradeHistory()
            stats = db.get_statistics()
            last_trades = db.get_trades(10)
            db.close()
            return {
                "statistics": stats,
                "last_10_trades": last_trades
            }
        except Exception as e:
            return {"error": f"Failed to read SQLite: {e}"}

    def _collect_source_code(self) -> Dict[str, Any]:
        src_dir = self.project_root / "src"
        if not src_dir.exists():
            return {"files": {}, "dependency_graph": {}, "architecture_summary": "Папка src не найдена"}

        files_data = {}
        imports_graph = {}

        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]

            for file in files:
                if not file.endswith('.py'):
                    continue
                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(src_dir)).replace('\\', '/')

                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.splitlines(keepends=True)
                except Exception as e:
                    content = f"# ERROR reading file: {e}"
                    lines = [content]

                docstring = ""
                imports = []
                try:
                    tree = ast.parse(content)
                    docstring = ast.get_docstring(tree) or ""
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append(node.module)
                except SyntaxError:
                    pass

                # Собираем информацию об отступах
                line_info = []
                for i, line in enumerate(lines):
                    stripped = line.lstrip('\n')
                    if stripped:
                        indent_len = len(line) - len(stripped)
                        indent_char = line[0] if indent_len > 0 else ' '
                        line_info.append({
                            "lineno": i + 1,
                            "indent_length": indent_len,
                            "indent_char": indent_char if indent_char in (' ', '\t') else ' ',
                            "content": stripped.rstrip('\n')
                        })
                    else:
                        line_info.append({
                            "lineno": i + 1,
                            "indent_length": 0,
                            "indent_char": ' ',
                            "content": ""
                        })

                files_data[rel_path] = {
                    "content": content,
                    "lines": line_info,  # детальная информация об отступах
                    "docstring": docstring,
                    "imports": imports,
                }

        # Строим граф зависимостей
        for rel_path, data in files_data.items():
            module_name = rel_path.replace('/', '.').replace('.py', '')
            imported_modules = set()
            for imp in data["imports"]:
                if imp.startswith('src.'):
                    target_module = imp[4:]
                    target_path = target_module.replace('.', '/') + '.py'
                    if target_path in files_data:
                        imported_modules.add(target_module)
                else:
                    pass
            imports_graph[module_name] = list(imported_modules)

        architecture_summary = self._generate_architecture_summary(files_data, imports_graph)

        return {
            "files": files_data,
            "dependency_graph": imports_graph,
            "architecture_summary": architecture_summary,
        }

    def _generate_architecture_summary(self, files_data: Dict, graph: Dict) -> str:
        modules_by_package = {}
        for path in files_data:
            parts = path.split('/')
            if len(parts) > 1:
                pkg = parts[0]
                modules_by_package.setdefault(pkg, []).append(path)

        lines = []
        lines.append("=== АРХИТЕКТУРА ПРОЕКТА ===\n")
        lines.append(f"Всего модулей: {len(files_data)}")
        lines.append("\nСтруктура по пакетам:")
        for pkg, mods in sorted(modules_by_package.items()):
            lines.append(f"  {pkg}/ ({len(mods)} файлов)")

        lines.append("\nКлючевые компоненты:")
        if 'core/engine/trading_engine.py' in files_data:
            lines.append("  - TradingEngine (core/engine/trading_engine.py) – главный цикл, управление позициями")
        if 'core/exit/exit_manager.py' in files_data:
            lines.append("  - ExitManager (core/exit/exit_manager.py) – проверка условий выхода")
        if 'core/scanner/market_scanner.py' in files_data:
            lines.append("  - MarketScanner (core/scanner/market_scanner.py) – поиск торговых сигналов")
        if 'core/executor/trade_executor.py' in files_data:
            lines.append("  - TradeExecutor (core/executor/trade_executor.py) – исполнение входов")

        lines.append("\nВнешние зависимости (основные):")
        lines.append("  - ccxt – взаимодействие с BingX API")
        lines.append("  - pandas, numpy – обработка данных")
        lines.append("  - PyQt5 – графический интерфейс")
        lines.append("  - scikit-learn, xgboost – машинное обучение")

        return "\n".join(lines)

    def _collect_advanced_stats(self) -> Dict:
        try:
            from src.utils.sqlite_history import SQLiteTradeHistory
            db = SQLiteTradeHistory()
            trades = db.get_trades(1000)
            db.close()
        except Exception as e:
            return {"error": str(e)}
        if not trades:
            return {"total_trades": 0}
        total = len(trades)
        wins = [t for t in trades if float(t.get("pnl", 0)) > 0]
        losses = [t for t in trades if float(t.get("pnl", 0)) <= 0]
        win_count = len(wins)
        total_pnl = sum(float(t.get("pnl", 0)) for t in trades)
        hour_stats = {h: {"trades": 0, "pnl": 0.0} for h in range(24)}
        for t in trades:
            try:
                hour = datetime.fromisoformat(t["timestamp"].replace('Z', '+00:00')).hour
                hour_stats[hour]["trades"] += 1
                hour_stats[hour]["pnl"] += float(t.get("pnl", 0))
            except:
                pass
        best_hour = max(hour_stats.items(), key=lambda x: x[1]["pnl"]) if hour_stats else None
        worst_hour = min(hour_stats.items(), key=lambda x: x[1]["pnl"]) if hour_stats else None
        symbol_stats = {}
        for t in trades:
            sym = t.get("symbol", "UNKNOWN")
            symbol_stats.setdefault(sym, {"trades": 0, "pnl": 0.0, "wins": 0})
            symbol_stats[sym]["trades"] += 1
            symbol_stats[sym]["pnl"] += float(t.get("pnl", 0))
            if float(t.get("pnl", 0)) > 0:
                symbol_stats[sym]["wins"] += 1
        best_symbol = max(symbol_stats.items(), key=lambda x: x[1]["pnl"]) if symbol_stats else None
        worst_symbol = min(symbol_stats.items(), key=lambda x: x[1]["pnl"]) if symbol_stats else None
        cumulative = 0.0
        max_dd = 0.0
        peak = 0.0
        for t in sorted(trades, key=lambda x: x.get("timestamp", "")):
            cumulative += float(t.get("pnl", 0))
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return {
            "total_trades": total,
            "win_count": win_count,
            "loss_count": len(losses),
            "win_rate": round(win_count / total * 100, 1) if total else 0,
            "total_pnl": round(total_pnl, 4),
            "avg_win": round(sum(float(t.get("pnl", 0)) for t in wins) / len(wins), 4) if wins else 0,
            "avg_loss": round(sum(float(t.get("pnl", 0)) for t in losses) / len(losses), 4) if losses else 0,
            "max_drawdown": round(max_dd, 4),
            "best_hour": {"hour": best_hour[0], "pnl": round(best_hour[1]["pnl"], 2)} if best_hour else None,
            "worst_hour": {"hour": worst_hour[0], "pnl": round(worst_hour[1]["pnl"], 2)} if worst_hour else None,
            "best_symbol": {"symbol": best_symbol[0], "pnl": round(best_symbol[1]["pnl"], 2)} if best_symbol else None,
            "worst_symbol": {"symbol": worst_symbol[0], "pnl": round(worst_symbol[1]["pnl"], 2)} if worst_symbol else None,
            "symbol_breakdown": dict(sorted(symbol_stats.items(), key=lambda x: abs(x[1]["pnl"]), reverse=True)[:5])
        }

    def suggest_improvements(self) -> List[Dict[str, str]]:
        return [
            {
                "id": "dynamic_tp",
                "title": "Динамический тейк-профит на основе ATR",
                "description": "TP рассчитывается как ATR * коэффициент (зависит от ADX).",
                "status": "уже реализовано в TradeExecutor"
            },
            {
                "id": "neural_filter",
                "title": "Включение нейросетевого фильтра",
                "description": "Активировать NeuralPredictor после накопления 50 сделок.",
                "status": "реализовано, требуется только накопление истории"
            },
            {
                "id": "genetic_optimizer",
                "title": "Генетическая оптимизация порогов индикаторов",
                "description": "Раз в сутки запускать GeneticOptimizer для подбора RSI/ADX/ATR.",
                "status": "модуль genetic_optimizer.py создан, нужно интегрировать в Engine"
            },
            {
                "id": "correlation_limit",
                "title": "Корреляционный лимит позиций",
                "description": "Не более 1 позиции в группе (BTC/ETH, мемкоины и т.д.).",
                "status": "реализовано в RiskController"
            },
            {
                "id": "web_ui",
                "title": "Веб-интерфейс",
                "description": "Flask-сервер с дашбордом, графиками и кнопками управления.",
                "status": "базовый вариант реализован (web/app.py)"
            },
            {
                "id": "auto_deploy",
                "title": "Автоматический деплой на VPS",
                "description": "Скрипт deploy.ps1 для установки зависимостей и создания задачи в планировщике.",
                "status": "скрипт создан"
            },
            {
                "id": "encrypt_keys",
                "title": "Шифрование API ключей",
                "description": "Хранить ключи зашифрованными с мастер-паролем из переменной окружения.",
                "status": "реализовано в security/key_encryption.py"
            },
            {
                "id": "ml_ensemble",
                "title": "Ансамбль ML моделей (RandomForest + XGBoost)",
                "description": "Обучать раз в неделю и использовать для фильтрации сигналов.",
                "status": "модули ml/ созданы, требуется интеграция"
            },
            {
                "id": "profit_target",
                "title": "Остановка при достижении дневной цели",
                "description": "При достижении N% прибыли за день бот перестаёт открывать новые позиции.",
                "status": "реализовано в Engine (daily_profit_target)"
            },
        ]

    def _get_patcher_instructions(self) -> str:
        return (
            "╔══════════════════════════════════════════════════════════════════════════════╗\n"
            "║           ИНСТРУКЦИЯ ДЛЯ ИИ: СОЗДАНИЕ ПАТЧЕЙ ДЛЯ SafePatcher v3.3          ║\n"
            "║                    (стандартный unified diff без a/b)                        ║\n"
            "╚══════════════════════════════════════════════════════════════════════════════╝\n\n"
            "⚡ ФОРМАТ ПАТЧА (ОБЯЗАТЕЛЬНО!):\n"
            "   Патч должен быть в формате unified diff. Заголовки:\n"
            "   --- src/путь/к/исходному/файлу\n"
            "   +++ src/путь/к/изменённому/файлу\n"
            "   (без префиксов a/ и b/)\n\n"
            "   Затем следуют один или несколько блоков изменений (hunk):\n"
            "   @@ -старый_номер,старое_количество +новый_номер,новое_количество @@\n"
            "   Контекстные строки начинаются с пробела.\n"
            "   Удаляемые строки начинаются с '-'.\n"
            "   Добавляемые строки начинаются с '+'.\n\n"
            "🧪 ПРИМЕР:\n"
            "--- src/utils/api_client.py\n"
            "+++ src/utils/api_client.py\n"
            "@@ -24,7 +24,7 @@ class AsyncBingXClient:\n"
            "         self.max_retries = 5\n"
            "         self.retry_delay = 1.0\n"
            "-        self.timeout = 20\n"
            "+        self.timeout = 30\n"
            "         self.logger = BotLogger(level=\"INFO\")\n\n"
            "❗ ВАЖНО:\n"
            "   - Пути должны быть относительно корня проекта (где лежит safe_patcher.py).\n"
            "   - НЕ ИСПОЛЬЗУЙТЕ префиксы a/ и b/ в заголовках --- и +++.\n"
            "   - Отступы в строках должны точно совпадать с оригиналом.\n"
            "   - Применять патчи через `python safe_patcher.py --apply имя_файла.patch`.\n"
            "   - Перед применением SafePatcher проверит совпадение контекстных строк.\n"
        )

    def _get_ai_guidance(self) -> Dict:
        """Инструкция для ИИ по работе с данным экспортом."""
        return {
            "rules": [
                "Если в diagnostics.quick_fixes есть готовые замены — предложи пользователю выполнить их вручную (найти/заменить).",
                "Если нужный файл отсутствует в source_code.files или его содержимое неполное — НЕ генерируй патч вслепую.",
                "Вместо этого запроси у пользователя актуальное содержимое файла: 'Пришли мне файл src/путь/к/файлу.py, я создам точный патч.'",
                "После получения файла создай патч в формате SafePatcher v3.3 (без a/ и b/).",
                "Перед отправкой патча проверь, что контекстные строки точно совпадают с присланным файлом."
            ],
            "fallback_request_template": (
                "Для создания корректного патча мне нужно актуальное содержимое файла `{file_path}`.\n"
                "Пожалуйста, скопируй его текст и пришли сюда."
            ),
            "common_files_to_request": [
                "src/config/settings.py",
                "src/config/user_config.json",
                "src/core/risk/risk_manager.py",
                "src/utils/api_client.py"
            ],
            "note": "В source_code.files хранится код на момент экспорта, но он может быть устаревшим или минифицированным. Лучше запросить свежий файл."
        }

    def _build_diagnostics(self, stats: Dict, config: Dict) -> Dict:
        issues = []
        warnings = []
        quick_fixes = []

        # Проверка критических фильтров
        min_vol = config.get("min_volume_24h_usdt", 50000)
        if min_vol > 10000:
            issues.append({
                "type": "strict_filter",
                "param": "min_volume_24h_usdt",
                "current": min_vol,
                "recommended": 10000,
                "reason": "Слишком высокий порог объёма отсекает большинство пар при малом депозите."
            })
            quick_fixes.append({
                "file": "src/config/user_config.json",
                "action": "replace",
                "find": f'"min_volume_24h_usdt": {min_vol}',
                "replace": '"min_volume_24h_usdt": 10000'
            })

        min_atr = config.get("min_atr_percent", 1.5)
        if min_atr > 1.0:
            warnings.append({
                "param": "min_atr_percent",
                "current": min_atr,
                "recommended": 0.8,
                "reason": "В спокойном рынке ATR редко превышает 1.5%."
            })
            quick_fixes.append({
                "file": "src/config/user_config.json",
                "action": "replace",
                "find": f'"min_atr_percent": {min_atr}',
                "replace": '"min_atr_percent": 0.8'
            })

        min_adx = config.get("min_adx", 15)
        if min_adx > 12:
            warnings.append({
                "param": "min_adx",
                "current": min_adx,
                "recommended": 10,
                "reason": "ADX>15 отсекает слабые тренды."
            })
            quick_fixes.append({
                "file": "src/config/user_config.json",
                "action": "replace",
                "find": f'"min_adx": {min_adx}',
                "replace": '"min_adx": 10'
            })

        if not config.get("use_neural_predictor", False):
            warnings.append({
                "param": "use_neural_predictor",
                "current": False,
                "recommended": True,
                "reason": "Нейропредиктор улучшает фильтрацию сигналов после 50 сделок."
            })
            quick_fixes.append({
                "file": "src/config/user_config.json",
                "action": "replace",
                "find": '"use_neural_predictor": false',
                "replace": '"use_neural_predictor": true'
            })

        # Анализ торговой статистики
        total_trades = stats.get("total_trades", 0)
        if total_trades == 0:
            issues.append({
                "type": "no_trades",
                "reason": "Бот не совершил ни одной сделки. Проверьте фильтры и наличие сигналов."
            })
        elif total_trades > 0:
            win_rate = stats.get("win_rate", 0)
            if win_rate < 30:
                warnings.append({
                    "type": "low_winrate",
                    "current": win_rate,
                    "reason": "Низкий процент побед, стратегия требует оптимизации."
                })

        # Проверка ошибок API
        error_tail = self._collect_error_logs(20)
        if "timestamp is invalid" in error_tail:
            issues.append({
                "type": "timestamp_error",
                "reason": "Обнаружена ошибка синхронизации времени BingX API. Примените патч fix_timestamp.patch."
            })

        return {
            "issues": issues,
            "warnings": warnings,
            "quick_fixes": quick_fixes,
            "summary": {
                "total_trades": total_trades,
                "win_rate": stats.get("win_rate", 0),
                "total_pnl": stats.get("total_pnl", 0),
                "open_positions": len(self.engine_state.get("positions", {})) if self.engine_state else 0
            }
        }

    def _extract_engine_state(self) -> Dict:
        """Извлекает состояние движка, если доступно."""
        try:
            from src.core.engine.trading_engine import TradingEngine
            # Пытаемся найти активный движок через глобальную переменную или синглтон
            # Для простоты возвращаем заглушку, если не передано явно
            return {"error": "engine not provided"}
        except:
            return {"error": "could not extract engine state"}

    def _collect_performance_snapshot(self) -> Dict:
        """Собирает текущие метрики производительности."""
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            return {
                "cpu_percent": process.cpu_percent(interval=0.1),
                "memory_rss_mb": round(mem_info.rss / 1024 / 1024, 1),
                "memory_vms_mb": round(mem_info.vms / 1024 / 1024, 1),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections()),
            }
        except Exception as e:
            return {"error": str(e)}

    def _collect_error_logs(self, lines: int = 100) -> str:
        """Извлекает последние строки с уровнем ERROR или CRITICAL из логов."""
        log_dir = self.project_root / "data" / "logs"
        if not log_dir.exists():
            return ""
        log_files = sorted(log_dir.glob("*_bot.log"), reverse=True)
        if not log_files:
            return ""
        try:
            with open(log_files[0], 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                error_lines = [l for l in all_lines if "ERROR" in l or "CRITICAL" in l]
                return "".join(error_lines[-lines:])
        except Exception:
            return ""

    def _collect_market_context(self) -> Dict:
        """Собирает текущий снимок рынка (топ-5 пар по объёму)."""
        client = None
        try:
            from src.utils.api_client import BingXClient
            from src.config.settings import Settings
            settings = Settings()
            client = BingXClient(
                api_key=settings.get("api_key", ""),
                api_secret=settings.get("api_secret", ""),
                demo_mode=settings.get("demo_mode", True)
            )
            tickers = []
            for sym in ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]:
                try:
                    t = client.get_ticker(sym)
                    tickers.append({
                        "symbol": sym,
                        "price": t.get("lastPrice", 0),
                        "volume24h": t.get("volume24h", 0),
                        "change24h": t.get("change24h", 0)
                    })
                except:
                    pass
            return {"top_pairs": tickers}
        except Exception as e:
            return {"error": str(e)}
        finally:
            if client:
                client.close()

    def _collect_recent_scans(self) -> Dict:
        """Пытается получить результаты последнего сканирования."""
        # Заглушка, можно расширить при интеграции с MarketScanner
        return {"note": "recent scan data not available in exporter"}

    def generate_export(self, trigger_reason: str = "manual", minify_source: bool = True, diff_only: bool = True) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = self.export_dir / f"AI_EXPORT_v2_{trigger_reason}_{timestamp}.json"

        self.logger.info("Сбор исходного кода...")
        source_data = self._collect_source_code()

        # Diff-оптимизация
        if diff_only and self.previous_export:
            prev_files = self.previous_export.get("source_code", {}).get("files", {})
            filtered = {}
            for path, data in source_data.get("files", {}).items():
                prev = prev_files.get(path, {})
                if prev.get("content") == data.get("content"):
                    filtered[path] = {"hash": self._file_hash(data.get("content", "")), "unchanged": True}
                else:
                    if minify_source:
                        data["content"] = self._minify_python(data.get("content", ""))
                    filtered[path] = data
            source_data["files"] = filtered
            changed = sum(1 for v in filtered.values() if not v.get("unchanged"))
            self.logger.info(f"Diff-режим: {changed} изменённых файлов")
        elif minify_source:
            for path, data in source_data.get("files", {}).items():
                if "content" in data:
                    data["content"] = self._minify_python(data["content"])

        self.logger.info("Сбор аналитики...")
        stats = self._collect_advanced_stats()

        # === НОВОЕ: диагностика и руководство для ИИ ===
        diagnostics = self._build_diagnostics(stats, self.config)

        # Сбор дополнительных данных
        performance_snapshot = self._collect_performance_snapshot()
        error_logs = self._collect_error_logs(100)
        market_context = self._collect_market_context()
        recent_scans = self._collect_recent_scans()

        try:
            mem = psutil.virtual_memory()
            sys_info = {
                "os": platform.system(),
                "python": platform.python_version(),
                "ram_gb": round(mem.total / (1024**3), 1),
                "cpu_cores": os.cpu_count()
            }
        except:
            sys_info = {}

        engine_state_data = self.engine_state
        if not engine_state_data and hasattr(self, '_engine_ref'):
            engine_state_data = self._extract_engine_state()

        export_data = {
            "version": "2.1",
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger_reason,
            "config": self.config,
            "weights": self.weights,
            "engine_state": self.engine_state,
            "system": sys_info,
            "trade_analytics": stats,
            "source_code": source_data,
            "previous_export_reference": self.previous_export.get("timestamp") if self.previous_export else None,
            "improvement_suggestions": self.suggest_improvements(),
            "patcher_instructions": self._get_patcher_instructions(),
            "performance_snapshot": performance_snapshot,
            "error_logs_tail": error_logs,
            "market_context": market_context,
            "recent_scans": recent_scans,
            # Новые поля
            "diagnostics": diagnostics,
            "ai_guidance": self._get_ai_guidance(),
        }

        raw_json = json.dumps(export_data, ensure_ascii=False)
        size_kb = len(raw_json.encode('utf-8')) / 1024
        export_data["meta"] = {
            "size_kb": round(size_kb, 1),
            "estimated_tokens": int(size_kb * 0.25),
            "compression": "minified" if minify_source else "none",
            "diff_mode": diff_only
        }

        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=1, ensure_ascii=False)
            self.logger.info(f"📄 AI Export v2: {export_file} ({size_kb:.1f} KB)")
            return str(export_file)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения: {e}")
            return ""
