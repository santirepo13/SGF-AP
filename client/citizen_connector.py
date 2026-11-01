"""Citizen report API operations built on the shared authenticated transport."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from urllib.parse import quote

from .transport import RegistrationTransport


class CitizenReportConnector(Protocol):
    def register_report(self, payload: Mapping[str, object]) -> object: ...
    def find_matches(self, *, address_id: int, failure_type_id: int) -> object: ...
    def get_report_attempt(self, *, request_key: str) -> object: ...
    def create_or_reuse_address(self, payload: Mapping[str, object]) -> object: ...
    def list_catalog(self, path: str) -> object: ...


class HttpCitizenReportConnector:
    """Keep citizen-specific paths out of Flet views and controllers."""

    def __init__(self, transport: RegistrationTransport) -> None:
        self._transport = transport

    def register_report(self, payload: Mapping[str, object]) -> object:
        return self._transport.post_json(
            "/tickets/citizen",
            payload,
            requires_identity=True,
        )

    def find_matches(self, *, address_id: int, failure_type_id: int) -> object:
        return self._transport.post_json(
            "/tickets/citizen/matches",
            {"address_id": address_id, "failure_type_id": failure_type_id},
            requires_identity=True,
        )

    def get_report_attempt(self, *, request_key: str) -> object:
        return self._transport.get_json(
            f"/tickets/citizen/attempts/{quote(request_key, safe='')}",
            requires_identity=True,
        )

    def create_or_reuse_address(self, payload: Mapping[str, object]) -> object:
        return self._transport.post_json(
            "/addresses",
            payload,
            requires_identity=True,
        )

    def list_catalog(self, path: str) -> object:
        if type(path) is not str or not path.startswith("/catalogs/"):
            raise ValueError("catalog path must be an absolute catalog endpoint")
        return self._transport.get_json(path)


__all__ = ["CitizenReportConnector", "HttpCitizenReportConnector"]
