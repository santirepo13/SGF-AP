"""Service contracts, grouped by application domain."""

from .address import *
from .geolocation import *
from .tickets import *
from .users import *

__all__ = [name for name in globals() if name.endswith("ServiceInterface")]
