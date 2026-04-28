#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Log Rotator v1.0
Ротация по размеру + gzip. Очистка старых.
"""
import os
import gzip
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import List

logger = logging.getLogger(__name__)

class GzipRotator:
    def __call__(self, source: str, dest: str):
        gz_dest = f"{dest}.gz"
        with open(source, 'rb') as f_in:
            with gzip.open(gz_dest, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)

class LogRotator:
    @staticmethod
    def setup(
        log_path: str,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 10,
        encoding: str = "utf-8"
    ) -> RotatingFileHandler:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding
        )
        handler.rotator = GzipRotator()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        return handler

    @staticmethod
    def cleanup_old_logs(log_dir: str, days: int = 30):
        cutoff = datetime.now() - timedelta(days=days)
        log_path = Path(log_dir)
        removed = 0
        for f in log_path.glob("*.log*"):
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        f.unlink()
                        removed += 1
                    except Exception as e:
                        logger.error(f"Failed to remove old log {f}: {e}")
        if removed:
            logger.info(f"Cleaned up {removed} old log files")
        return removed

    @staticmethod
    def get_log_stats(log_dir: str) -> dict:
        log_path = Path(log_dir)
        total_size = 0
        file_count = 0
        for f in log_path.glob("*.log*"):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1
        return {
            "directory": log_dir,
            "file_count": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
