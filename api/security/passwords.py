"""Password hashing primitives used by account creation and authentication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

try:  # Keep imports of the API package usable before dependencies are installed.
    from argon2 import PasswordHasher
    from argon2.low_level import Type
except ModuleNotFoundError:  # pragma: no cover - exercised only in an uninstalled environment.
    PasswordHasher = None  # type: ignore[assignment,misc]
    Type = None  # type: ignore[assignment,misc]


@dataclass(frozen=True, slots=True)
class PasswordHashingConfig:
    """Central Argon2id cost parameters.

    The defaults follow the high-level ``argon2-cffi`` PasswordHasher defaults
    while making the selected algorithm explicit.
    """

    time_cost: int = 3
    memory_cost: int = 65536
    parallelism: int = 4
    hash_len: int = 32
    salt_len: int = 16

    def __post_init__(self) -> None:
        for name in ("time_cost", "memory_cost", "parallelism", "hash_len", "salt_len"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


class PasswordHasherInterface(Protocol):
    def hash(self, password: str) -> str: ...


class Argon2idPasswordHasher:
    """Generate complete, self-describing Argon2id encoded hashes."""

    def __init__(self, config: PasswordHashingConfig | None = None) -> None:
        if PasswordHasher is None or Type is None:
            raise RuntimeError("argon2-cffi is required to generate password hashes")
        settings = config or PasswordHashingConfig()
        self.config = settings
        self._hasher = PasswordHasher(
            time_cost=settings.time_cost,
            memory_cost=settings.memory_cost,
            parallelism=settings.parallelism,
            hash_len=settings.hash_len,
            salt_len=settings.salt_len,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        """Hash the exact supplied text; do not trim or normalize it."""

        if type(password) is not str:
            raise TypeError("password must be a string")
        if password == "":
            raise ValueError("password must not be empty")
        return self._hasher.hash(password)

    generate = hash
    generate_hash = hash
    hash_password = hash

    def verify(self, encoded_hash: str, password: str) -> bool:
        """Verify a password using the parameters embedded in its hash."""

        if type(encoded_hash) is not str or type(password) is not str:
            return False
        try:
            return bool(self._hasher.verify(encoded_hash, password))
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"{type(self).__name__}(config={self.config!r})"


class LazyArgon2idPasswordHasher:
    """Composition-safe wrapper that loads argon2 only when registration runs."""

    def __init__(self, config: PasswordHashingConfig | None = None) -> None:
        self.config = config
        self._delegate: Argon2idPasswordHasher | None = None

    def _component(self) -> Argon2idPasswordHasher:
        if self._delegate is None:
            self._delegate = Argon2idPasswordHasher(self.config)
        return self._delegate

    def hash(self, password: str) -> str:
        return self._component().hash(password)

    generate = hash
    generate_hash = hash
    hash_password = hash

    def verify(self, encoded_hash: str, password: str) -> bool:
        return self._component().verify(encoded_hash, password)


# Names that describe the component naturally to service composition code.
PasswordHashGenerator = Argon2idPasswordHasher
Argon2PasswordHasher = Argon2idPasswordHasher
PasswordHashService = Argon2idPasswordHasher


def generate_password_hash(
    password: str,
    *,
    hasher: PasswordHasherInterface | None = None,
) -> str:
    """Generate one hash through an injected or default Argon2id component."""

    component = hasher or Argon2idPasswordHasher()
    return component.hash(password)


__all__ = [
    "Argon2idPasswordHasher",
    "Argon2PasswordHasher",
    "LazyArgon2idPasswordHasher",
    "PasswordHashGenerator",
    "PasswordHashService",
    "PasswordHasherInterface",
    "PasswordHashingConfig",
    "generate_password_hash",
]
