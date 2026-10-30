"""Password hashing and verification primitives for account authentication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from api.errors import ApplicationError

try:  # Keep API imports usable before optional runtime dependencies are installed.
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
    from argon2.low_level import Type
except ModuleNotFoundError:  # pragma: no cover - exercised only in an uninstalled environment.
    PasswordHasher = None  # type: ignore[assignment,misc]
    Type = None  # type: ignore[assignment,misc]
    InvalidHashError = VerificationError = VerifyMismatchError = ()  # type: ignore[assignment,misc]


@dataclass(frozen=True, slots=True)
class PasswordHashingConfig:
    """Central Argon2id cost parameters."""

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

    def verify_password(self, password_hash: str, password: str) -> bool: ...


class Argon2idPasswordHasher:
    """Generate and verify complete, self-describing Argon2id encoded hashes."""

    def __init__(self, config: PasswordHashingConfig | None = None) -> None:
        if PasswordHasher is None or Type is None:
            raise RuntimeError("argon2-cffi is required to handle password hashes")
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

    def verify_password(self, password_hash: str, password: str) -> bool:
        """Compare a candidate with its stored Argon2id hash.

        A normal mismatch is the only verification failure that becomes
        ``False``. A damaged hash or an unavailable cryptographic component is
        an internal condition and is deliberately represented as ``SYS-002``.
        """

        if type(password_hash) is not str or type(password) is not str:
            raise ApplicationError.unexpected(cause=TypeError("password hash and password must be strings"))
        try:
            return bool(self._hasher.verify(password_hash, password))
        except VerifyMismatchError:
            return False
        except (InvalidHashError, VerificationError) as error:
            raise ApplicationError.unexpected(cause=error) from error
        except ApplicationError:
            raise
        except BaseException as error:
            raise ApplicationError.unexpected(cause=error) from error

    # ``verify`` remains available to existing callers while the explicit name
    # makes the password/hash argument order unambiguous for login code.
    verify = verify_password

    def __repr__(self) -> str:
        return f"{type(self).__name__}(config={self.config!r})"


class LazyArgon2idPasswordHasher:
    """Composition-safe wrapper that loads argon2 only when it is first used."""

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

    def verify_password(self, password_hash: str, password: str) -> bool:
        return self._component().verify_password(password_hash, password)

    verify = verify_password


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


def verify_password(
    password_hash: str,
    password: str,
    *,
    hasher: PasswordHasherInterface | None = None,
) -> bool:
    """Verify a candidate password without exposing either sensitive value."""

    component = hasher or Argon2idPasswordHasher()
    method = getattr(component, "verify_password", None) or getattr(component, "verify", None)
    if not callable(method):
        raise ApplicationError.unexpected(cause=TypeError("password verification component is not callable"))
    try:
        return bool(method(password_hash, password))
    except ApplicationError:
        raise
    except BaseException as error:
        raise ApplicationError.unexpected(cause=error) from error


__all__ = [
    "Argon2idPasswordHasher",
    "Argon2PasswordHasher",
    "LazyArgon2idPasswordHasher",
    "PasswordHashGenerator",
    "PasswordHashService",
    "PasswordHasherInterface",
    "PasswordHashingConfig",
    "generate_password_hash",
    "verify_password",
]
