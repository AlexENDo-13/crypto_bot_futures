#!/usr/bin/env python3
import logging, logging.handlers, sys, os, json, traceback, threading
from datetime import datetime
from typing import Dict, Any

class ColoredFormatter(logging.Formatter):
    COLORS = {"DEBUG":"\033[90m","INFO":"\033[96m","WARNING":"\033[93m","ERROR":"\033[91m","CRITICAL":"\033[95m","RESET":"\033[0m"}
    def format(self, record):
        c = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        record.levelname_colored = f"{c}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {"timestamp": datetime.utcnow().isoformat()+"Z","level":record.levelname,"logger":record.name,"message":record.getMessage(),"module":record.module,"function":record.funcName,"line":record.lineno}
        if record.exc_info: entry["exception"] = traceback.format_exception(*record.exc_info)
        if hasattr(record, "extra_data"): entry["extra"] = record.extra_data
        return json.dumps(entry, ensure_ascii=False)

class MetricsHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.errors_count = 0; self.warnings_count = 0; self.trades_count = 0; self.scans_count = 0
        self._lock = threading.Lock()
    def emit(self, record):
        with self._lock:
            msg = record.getMessage()
            if record.levelno >= logging.ERROR: self.errors_count += 1
            elif record.levelno >= logging.WARNING: self.warnings_count += 1
            if "Ордер исполнен" in msg or "Позиция открыта" in msg: self.trades_count += 1
            if "Сканирование рынка" in msg: self.scans_count += 1
    def get_metrics(self):
        with self._lock: return {"errors":self.errors_count,"warnings":self.warnings_count,"trades":self.trades_count,"scans":self.scans_count}
    def reset(self):
        with self._lock: self.errors_count = self.warnings_count = self.trades_count = self.scans_count = 0

class BotLogger:
    def __init__(self, name="BotLogger", level="INFO", log_dir="logs", max_bytes=10485760, backup_count=10):
        self.name = name
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.handlers = []
        self.logger.propagate = False
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        console.setFormatter(ColoredFormatter("%(asctime)s │ %(levelname_colored)s │ %(name)s │ %(message)s", datefmt="%H:%M:%S"))
        self.logger.addHandler(console)
        fh = logging.handlers.RotatingFileHandler(os.path.join(log_dir, f"{name.lower()}.log"), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        self.logger.addHandler(fh)
        jh = logging.handlers.RotatingFileHandler(os.path.join(log_dir, f"{name.lower()}.jsonl"), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        jh.setLevel(logging.DEBUG); jh.setFormatter(JSONFormatter()); self.logger.addHandler(jh)
        self.metrics = MetricsHandler(); self.metrics.setLevel(logging.INFO); self.logger.addHandler(self.metrics)
        dh = logging.handlers.RotatingFileHandler(os.path.join(log_dir, "decisions.jsonl"), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        dh.setLevel(logging.INFO); dh.setFormatter(JSONFormatter())
        self._decision_logger = logging.getLogger(f"{name}.decisions")
        self._decision_logger.setLevel(logging.INFO); self._decision_logger.handlers = [dh]; self._decision_logger.propagate = False
        eh = logging.handlers.RotatingFileHandler(os.path.join(log_dir, "errors.log"), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        eh.setLevel(logging.ERROR); eh.setFormatter(logging.Formatter("%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        self.logger.addHandler(eh)
        self.info(f"📝 Логгер инициализирован: {log_dir}/")
    def debug(self, msg, extra=None): self._log(logging.DEBUG, msg, extra)
    def info(self, msg, extra=None): self._log(logging.INFO, msg, extra)
    def warning(self, msg, extra=None): self._log(logging.WARNING, msg, extra)
    def error(self, msg, exc_info=False, extra=None): self._log(logging.ERROR, msg, extra, exc_info=exc_info)
    def critical(self, msg, exc_info=False, extra=None): self._log(logging.CRITICAL, msg, extra, exc_info=exc_info)
    def _log(self, level, msg, extra=None, exc_info=False):
        if extra: self.logger.log(level, msg, exc_info=exc_info, extra={"extra_data": extra})
        else: self.logger.log(level, msg, exc_info=exc_info)
    def log_decision(self, decision_type, symbol=None, data=None):
        self._decision_logger.info(json.dumps({"type":decision_type,"symbol":symbol,"timestamp":datetime.utcnow().isoformat()+"Z","data":data or {}}, ensure_ascii=False))
    def log_state(self, component, state):
        self._decision_logger.info(json.dumps({"type":"state","component":component,"state":state,"timestamp":datetime.utcnow().isoformat()+"Z"}, ensure_ascii=False))
    def log_trade(self, symbol, side, entry, qty, leverage, sl, tp, pnl=None, reason=None):
        self._decision_logger.info(json.dumps({"type":"trade","symbol":symbol,"side":side,"entry_price":entry,"quantity":qty,"leverage":leverage,"sl":sl,"tp":tp,"pnl":pnl,"reason":reason,"timestamp":datetime.utcnow().isoformat()+"Z"}, ensure_ascii=False))
    def get_metrics(self): return self.metrics.get_metrics()
    def reset_metrics(self): self.metrics.reset()
