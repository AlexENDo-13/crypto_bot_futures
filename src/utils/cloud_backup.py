#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud Backup v1.0
Бэкап ключей и БД на Яндекс.Диск / Mail.ru Облако.
"""
import logging
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class CloudBackup:
    """
    Бэкап в облако через WebDAV (Яндекс.Диск) или API.

    Usage:
        backup = CloudBackup(provider="yandex", token="OAuth_token")
        backup.backup_file("data/trades.db")
    """

    def __init__(self, provider: str = "yandex", token: str = "", 
                 backup_dir: str = "backups/cloud"):
        self.provider = provider.lower()
        self.token = token
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._webdav_url = self._get_webdav_url()

    def _get_webdav_url(self) -> str:
        if self.provider == "yandex":
            return "https://webdav.yandex.ru"
        elif self.provider == "mailru":
            return "https://webdav.cloud.mail.ru"
        return ""

    def backup_file(self, filepath: str, remote_folder: str = "crypto_bot") -> bool:
        """Загрузить файл в облако."""
        try:
            import requests

            local_path = Path(filepath)
            if not local_path.exists():
                logger.error(f"File not found: {filepath}")
                return False

            remote_path = f"{self._webdav_url}/{remote_folder}/{local_path.name}"

            with open(local_path, 'rb') as f:
                response = requests.put(
                    remote_path,
                    data=f,
                    headers={"Authorization": f"OAuth {self.token}"},
                    timeout=30
                )

            if response.status_code in (201, 204):
                logger.info(f"✅ Backed up: {local_path.name} → {self.provider}")
                return True
            else:
                logger.error(f"Backup failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Backup error: {e}")
            return False

    def backup_database(self, db_path: str = "data/trades.db") -> bool:
        """Бэкап БД с таймстампом."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"trades_{timestamp}.db"

        # Локальная копия
        local_backup = self.backup_dir / backup_name
        import shutil
        shutil.copy2(db_path, local_backup)

        # Облачная копия
        return self.backup_file(str(local_backup))

    def auto_backup_scheduler(self, interval_hours: int = 24):
        """Запустить периодический бэкап (в отдельном потоке)."""
        import threading
        import time

        def backup_loop():
            while True:
                time.sleep(interval_hours * 3600)
                self.backup_database()

        thread = threading.Thread(target=backup_loop, daemon=True, name="CloudBackup")
        thread.start()
        logger.info(f"Auto-backup started: every {interval_hours}h")
