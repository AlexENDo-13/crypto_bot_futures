#!/usr/bin/env python3
import os, base64
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

class KeyEncryption:
    def __init__(self, password=None, salt_path="data/security/salt.bin"):
        self.salt_path = salt_path
        os.makedirs(os.path.dirname(salt_path), exist_ok=True)
        self.salt = self._load_or_create_salt()
        self.password = password or os.environ.get("BOT_ENCRYPTION_KEY", "default_password_change_me")
        if HAS_CRYPTO: self.fernet = self._create_fernet()
        else: self.fernet = None
    def _load_or_create_salt(self):
        if os.path.exists(self.salt_path):
            with open(self.salt_path, "rb") as f: return f.read()
        salt = os.urandom(16)
        with open(self.salt_path, "wb") as f: f.write(salt)
        return salt
    def _create_fernet(self):
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=self.salt, iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(self.password.encode()))
        return Fernet(key)
    def encrypt(self, data):
        if not self.fernet: return data
        return self.fernet.encrypt(data.encode()).decode()
    def decrypt(self, token):
        if not self.fernet: return token
        return self.fernet.decrypt(token.encode()).decode()
