"""Framework-neutral client components for registration and login flows."""

from .authentication import AuthState, AuthenticatedSession, AuthenticationState, SUPPORTED_ROLE_NAMES
from .config import load_client_config
from .design_tokens import ALLOWED_TEXT_PAIRS, COLORS, ColorToken, INTERACTION_MATRIX, contrast_ratio, validate_palette
from .http_connector import LoginHttpConnector, RegistrationHttpConnector, build_login_connector, build_registration_connector
from .login import LoginAttempt, LoginConnector, LoginController, LoginFormState, LoginOutput, LoginState, LoginStatus
from .navigation import NavigationController, ROLE_DESTINATIONS, ScreenName
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
    "NavigationController",
    "ROLE_DESTINATIONS",
    "RegistrationAttempt",
    "RegistrationConnector",
    "RegistrationController",
    "RegistrationFormState",
    "RegistrationHttpConnector",
    "RegistrationState",
    "RegistrationStatus",
    "RegistrationTransport",
    "SUPPORTED_ROLE_NAMES",
    "ScreenName",
    "build_login_connector",
    "build_registration_connector",
    "contrast_ratio",
    "load_client_config",
    "validate_palette",
]
