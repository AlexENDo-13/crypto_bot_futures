"""
Key Encryption Module – шифрование API ключей на диске.
"""

import os
import base64
import json
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class KeyEncryption:
    ENV_VAR = "BINGX_MASTER_PASSWORD"
    CONFIG_PATH = Path("src/config/user_config.json")
    SALT_FILE = Path("data/security/salt.bin")

    def __init__(self):
        self.salt = self._get_or_create_salt()
        self.cipher = self._get_cipher()

    def _get_or_create_salt(self) -> bytes:
        self.SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
        if self.SALT_FILE.exists():
            return self.SALT_FILE.read_bytes()
        else:
            salt = os.urandom(16)
            self.SALT_FILE.write_bytes(salt)
            return salt

    def _derive_key(self, password: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def _get_cipher(self) -> Optional[Fernet]:
        password = os.environ.get(self.ENV_VAR)
        if not password:
            print(f"⚠️ Переменная окружения {self.ENV_VAR} не установлена. Ключи НЕ зашифрованы.")
            return None
        key = self._derive_key(password)
        return Fernet(key)

    def ensure_keys_decrypted(self):
        """Проверяет, зашифрованы ли ключи в конфиге, и если да – расшифровывает."""
        if not self.CONFIG_PATH.exists():
            return

        try:
            with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    # Пустой файл – ничего не делаем, Settings сам заполнит позже
                    return
                config = json.loads(content)
        except (json.JSONDecodeError, IOError):
            # Файл поврежден или пуст – пропускаем, Settings разберется
            return

        api_key = config.get("api_key", "")
        api_secret = config.get("api_secret", "")

        modified = False
        if api_key.startswith("ENC:") and self.cipher:
            try:
                encrypted = api_key[4:].encode()
                config["api_key"] = self.cipher.decrypt(encrypted).decode()
                modified = True
            except Exception:
                pass

        if api_secret.startswith("ENC:") and self.cipher:
            try:
                encrypted = api_secret[4:].encode()
                config["api_secret"] = self.cipher.decrypt(encrypted).decode()
                modified = True
            except Exception:
                pass

        if modified:
            with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)

    def encrypt_config_keys(self):
        """Зашифровывает API ключи в конфиге (вызывается вручную)."""
        if not self.cipher:
            print("Невозможно зашифровать: мастер-пароль не установлен.")
            return

        if not self.CONFIG_PATH.exists():
            print("Конфиг не найден.")
            return

        try:
            with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    config = {}
                else:
                    config = json.loads(content)
        except (json.JSONDecodeError, IOError):
            print("Ошибка чтения конфига. Создайте корректный JSON файл.")
            return

        api_key = config.get("api_key", "")
        api_secret = config.get("api_secret", "")

        modified = False
        if api_key and not api_key.startswith("ENC:"):
            encrypted = self.cipher.encrypt(api_key.encode())
            config["api_key"] = "ENC:" + encrypted.decode()
            modified = True

        if api_secret and not api_secret.startswith("ENC:"):
            encrypted = self.cipher.encrypt(api_secret.encode())
            config["api_secret"] = "ENC:" + encrypted.decode()
            modified = True

        if modified:
            with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            print("Ключи зашифрованы.")
        else:
            print("Ключи уже зашифрованы или отсутствуют.")