"""
Security module - Encrypts API keys using Fernet (AES-256).
"""
import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class KeyManager:
    """
    Secure API key storage with encryption.
    Keys are encrypted at rest using a password-derived key.
    """

    def __init__(self, key_file: str = "data/state/.keys", password: str = None):
        self.key_file = Path(key_file)
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self._password = password or os.environ.get("BOT_PASSWORD", "default_password_change_me")
        self._fernet = self._init_fernet()
        self._keys: dict = {}
        self._load_keys()

    def _init_fernet(self) -> Fernet:
        """Initialize Fernet cipher from password"""
        salt = b"crypto_bot_salt_v5"  # In production, use random salt stored separately
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._password.encode()))
        return Fernet(key)

    def _load_keys(self):
        """Load encrypted keys from file"""
        if self.key_file.exists():
            try:
                with open(self.key_file, "rb") as f:
                    encrypted = f.read()
                    decrypted = self._fernet.decrypt(encrypted)
                    import json
                    self._keys = json.loads(decrypted.decode())
            except Exception:
                self._keys = {}

    def _save_keys(self):
        """Save encrypted keys to file"""
        import json
        encrypted = self._fernet.encrypt(json.dumps(self._keys).encode())
        with open(self.key_file, "wb") as f:
            f.write(encrypted)

    def set_key(self, name: str, value: str):
        """Store an encrypted key"""
        self._keys[name] = value
        self._save_keys()

    def get_key(self, name: str) -> str:
        """Retrieve a key"""
        return self._keys.get(name, "")

    def has_key(self, name: str) -> bool:
        return name in self._keys and self._keys[name]

    def delete_key(self, name: str):
        if name in self._keys:
            del self._keys[name]
            self._save_keys()
