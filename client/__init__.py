"""Framework-neutral client components for registration and login flows."""

from .access_continuity import AccessCoordinator, AccessState, AccessStatus
from .access_storage import (
    AccessStorage,
    AccessStorageCorrupted,
    AccessStorageError,
    AccessStorageUnavailable,
    MemoryAccessStorage,
    SecureAccessStorage,
    StoredAccess,
    UnavailableAccessStorage,
)
from .authentication import AuthState, AuthenticatedSession, AuthenticationState, SUPPORTED_ROLE_NAMES
from .config import load_client_config
from .design_tokens import ALLOWED_TEXT_PAIRS, COLORS, ColorToken, INTERACTION_MATRIX, contrast_ratio, validate_palette
from .http_connector import LoginHttpConnector, RegistrationHttpConnector, build_login_connector, build_registration_connector
from .login import LoginAttempt, LoginConnector, LoginController, LoginFormState, LoginOutput, LoginState, LoginStatus
from .navigation import NavigationController, PROTECTED_SCREENS, ROLE_DESTINATIONS, ScreenName
from .password_recovery import PasswordRecoveryController, PasswordRecoveryState, RecoveryStep
from .registration import (
    RegistrationAttempt,
    RegistrationConnector,
    RegistrationController,
    RegistrationFormState,
    RegistrationState,
    RegistrationStatus,
)
from .transport import (
    ApiTransport,
    ConnectorError,
    ConnectorResponse,
    ConnectorResponseError,
    ConnectorTimeoutError,
    ConnectorTransportError,
    RegistrationTransport,
)

__all__ = [
    "ALLOWED_TEXT_PAIRS",
    "AccessCoordinator",
    "AccessState",
    "AccessStatus",
    "AccessStorage",
    "AccessStorageCorrupted",
    "AccessStorageError",
    "AccessStorageUnavailable",
    "ApiTransport",
    "AuthState",
    "AuthenticatedSession",
    "AuthenticationState",
    "COLORS",
    "ColorToken",
    "ConnectorError",
    "ConnectorResponse",
    "ConnectorResponseError",
    "ConnectorTimeoutError",
    "ConnectorTransportError",
    "INTERACTION_MATRIX",
    "LoginAttempt",
    "LoginConnector",
    "LoginController",
    "LoginFormState",
    "LoginHttpConnector",
    "LoginOutput",
    "LoginState",
    "LoginStatus",
    "MemoryAccessStorage",
    "NavigationController",
    "PasswordRecoveryController",
    "PasswordRecoveryState",
    "PROTECTED_SCREENS",
    "ROLE_DESTINATIONS",
    "RegistrationAttempt",
    "RegistrationConnector",
    "RegistrationController",
    "RegistrationFormState",
    "RegistrationHttpConnector",
    "RegistrationState",
    "RegistrationStatus",
    "RegistrationTransport",
    "RecoveryStep",
    "SecureAccessStorage",
    "StoredAccess",
    "SUPPORTED_ROLE_NAMES",
    "ScreenName",
    "UnavailableAccessStorage",
    "build_login_connector",
    "build_registration_connector",
    "contrast_ratio",
    "load_client_config",
    "validate_palette",
]
