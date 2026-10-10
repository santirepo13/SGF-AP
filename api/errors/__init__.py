"""Central application error component for SGF-AP."""

from .application_error import ApplicationError
from .error_catalog import ErrorCatalog, ErrorDefinition
from .error_codes import ErrorCode
from .error_handler import ErrorHandler, PersistenceContext

__all__ = [
    "ApplicationError",
    "ErrorCatalog",
    "ErrorDefinition",
    "ErrorCode",
    "ErrorHandler",
    "PersistenceContext",
]
