"""bcrypt password hashing adapter."""

from __future__ import annotations


class BcryptPasswordHasher:
    """Hash passwords without leaking plaintext into application storage."""

    def __init__(self, *, rounds: int = 12) -> None:
        if rounds < 10:
            raise ValueError("bcrypt rounds must be at least 10")
        self._rounds = rounds

    def hash(self, password: str) -> str:
        import bcrypt

        _validate_password(password)
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=self._rounds),
        ).decode("utf-8")

    def verify(self, password: str, password_hash: str) -> bool:
        import bcrypt

        if not password or not password_hash:
            return False
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False


def _validate_password(password: str) -> None:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
