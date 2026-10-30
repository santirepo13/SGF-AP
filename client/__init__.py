"""Framework-neutral client components for the citizen-registration flow."""

from .config import load_client_config
from .design_tokens import ALLOWED_TEXT_PAIRS, COLORS, ColorToken, INTERACTION_MATRIX, contrast_ratio, validate_palette
from .http_connector import RegistrationHttpConnector, build_registration_connector
from .navigation import LoginFormState, NavigationController, ScreenName
from .transport import (
    ConnectorError,
    ConnectorResponse,
    ConnectorResponseError,
    ConnectorTimeoutError,
    ConnectorTransportError,
    RegistrationTransport,
)
from .registration import (
    RegistrationAttempt,
    RegistrationConnector,
    RegistrationController,
    RegistrationFormState,
    RegistrationState,
    RegistrationStatus,
)

__all__ = [
    "ALLOWED_TEXT_PAIRS",
    "COLORS",
    "ColorToken",
    "INTERACTION_MATRIX",
    "contrast_ratio",
    "validate_palette",
    "load_client_config",
    "LoginFormState",
    "NavigationController",
    "ScreenName",
    "RegistrationHttpConnector",
    "build_registration_connector",
    "ConnectorError",
    "ConnectorResponse",
    "ConnectorResponseError",
    "ConnectorTimeoutError",
    "ConnectorTransportError",
    "RegistrationTransport",
    "RegistrationAttempt",
    "RegistrationConnector",
    "RegistrationController",
    "RegistrationFormState",
    "RegistrationState",
    "RegistrationStatus",
]
