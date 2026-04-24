"""
CryptoBot v7.1 - Security utilities
"""
import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class KeyEncryption:
    """Encrypts API keys with a password-derived key."""

    def __init__(self, salt_path: str = "data/security/salt.bin"):
        self.salt_path = Path(salt_path)
        self.salt_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.salt_path.exists():
            self.salt = os.urandom(16)
            self.salt_path.write_bytes(self.salt)
        else:
            self.salt = self.salt_path.read_bytes()

    def _get_key(self, password: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt(self, data: str, password: str) -> str:
        f = Fernet(self._get_key(password))
        return f.encrypt(data.encode()).decode()

    def decrypt(self, token: str, password: str) -> str:
        f = Fernet(self._get_key(password))
        return f.decrypt(token.encode()).decode()
