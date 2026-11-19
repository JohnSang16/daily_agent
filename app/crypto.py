"""Encrypt bank access tokens at rest. The key lives only in the environment."""

from cryptography.fernet import Fernet


class TokenBox:
    def __init__(self, key: str):
        if not key:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set")
        self._f = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self._f.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._f.decrypt(value.encode()).decode()
