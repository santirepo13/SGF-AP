"""Citizen report API operations built on the shared authenticated transport."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol
from urllib.parse import quote

from .transport import MultipartFile, RegistrationTransport


class CitizenReportConnector(Protocol):
    def for_access_token(self, access_token: str) -> CitizenReportConnector: ...
    def register_report(self, payload: Mapping[str, object]) -> object: ...
    def find_matches(self, *, address_id: int, failure_type_id: int) -> object: ...
    def get_report_attempt(self, *, request_key: str) -> object: ...
    def create_or_reuse_address(self, payload: Mapping[str, object]) -> object: ...
    def list_catalog(self, path: str) -> object: ...
    def upload_photo(
        self,
        *,
        request_key: str,
        upload_key: str,
        capture_source: str,
        captured_at: str | None,
        file: MultipartFile,
        progress: Callable[[int, int], None] | None,
    ) -> object: ...
    def list_uploads(self, *, request_key: str) -> object: ...
    def delete_upload(self, *, upload_id: str) -> object: ...
    def contribute_evidence(self, payload: Mapping[str, object]) -> object: ...
    def get_contribution_attempt(self, *, request_key: str) -> object: ...
    def list_ticket_evidences(self, *, code: str) -> object: ...
    def list_contribution_evidences(self, *, contribution_id: str) -> object: ...
    def download_evidence(self, *, evidence_id: int) -> object: ...
    def list_my_reports(self, limit: int = 20, cursor: str | None = None) -> object: ...
    def get_my_report(self, code: str) -> object: ...
    def list_my_report_history(self, code: str, limit: int = 50, cursor: str | None = None) -> object: ...
    def get_public_report(self, code: str) -> object: ...


class HttpCitizenReportConnector:
    """Keep citizen-specific paths out of Flet views and controllers."""

    def __init__(self, transport: RegistrationTransport) -> None:
        self._transport = transport

    def for_access_token(self, access_token: str) -> HttpCitizenReportConnector:
        transport = self._transport.for_access_token(access_token)
        return HttpCitizenReportConnector(transport)

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

    def upload_photo(
        self,
        *,
        request_key: str,
        upload_key: str,
        capture_source: str,
        captured_at: str | None,
        file: MultipartFile,
        progress: Callable[[int, int], None] | None,
    ) -> object:
        return self._transport.post_multipart(
            "/evidences/uploads",
            fields={
                "request_key": request_key,
                "upload_key": upload_key,
                "capture_source": capture_source,
                **({"captured_at": captured_at} if captured_at else {}),
            },
            file=file,
            requires_identity=True,
            progress=progress,
        )

    def list_uploads(self, *, request_key: str) -> object:
        return self._transport.get_json(
            "/evidences/uploads",
            {"request_key": request_key},
            requires_identity=True,
        )

    def delete_upload(self, *, upload_id: str) -> object:
        return self._transport.delete_json(
            f"/evidences/uploads/{quote(upload_id, safe='')}",
            requires_identity=True,
        )

    def contribute_evidence(self, payload: Mapping[str, object]) -> object:
        return self._transport.post_json(
            "/tickets/citizen/contributions",
            payload,
            requires_identity=True,
        )

    def get_contribution_attempt(self, *, request_key: str) -> object:
        return self._transport.get_json(
            f"/tickets/citizen/contributions/attempts/{quote(request_key, safe='')}",
            requires_identity=True,
        )

    def list_ticket_evidences(self, *, code: str) -> object:
        return self._transport.get_json(
            f"/tickets/citizen/mine/{quote(code, safe='')}/evidences",
            requires_identity=True,
        )

    def list_contribution_evidences(self, *, contribution_id: str) -> object:
        return self._transport.get_json(
            f"/evidences/citizen/contributions/{quote(contribution_id, safe='')}",
            requires_identity=True,
        )

    def download_evidence(self, *, evidence_id: int) -> object:
        return self._transport.get_binary(
            f"/evidences/{evidence_id}/content",
            requires_identity=True,
            maximum_bytes=10_000_000,
        )

    def list_my_reports(self, limit: int = 20, cursor: str | None = None) -> object:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if cursor is not None and (type(cursor) is not str or not cursor or len(cursor) > 512):
            raise ValueError("cursor is invalid")
        return self._transport.get_json(
            "/tickets/citizen/mine",
            {"limit": limit, **({"cursor": cursor} if cursor is not None else {})},
            requires_identity=True,
        )

    def get_my_report(self, code: str) -> object:
        _validate_query_code(code)
        return self._transport.get_json(
            f"/tickets/citizen/mine/{quote(code, safe='')}", requires_identity=True
        )

    def list_my_report_history(self, code: str, limit: int = 50, cursor: str | None = None) -> object:
        _validate_query_code(code)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if cursor is not None and (type(cursor) is not str or not cursor or len(cursor) > 512):
            raise ValueError("cursor is invalid")
        return self._transport.get_json(
            f"/tickets/citizen/mine/{quote(code, safe='')}/history",
            {"limit": limit, **({"cursor": cursor} if cursor is not None else {})},
            requires_identity=True,
        )

    def get_public_report(self, code: str) -> object:
        _validate_query_code(code)
        return self._transport.get_json(
            f"/tickets/public/{quote(code, safe='')}", requires_identity=False
        )


def _validate_query_code(code: str) -> None:
    if type(code) is not str or not 1 <= len(code) <= 24 or not code.isascii():
        raise ValueError("code is invalid")
    if not code[0].isalnum() or any(not (character.isalnum() or character in "._-") for character in code):
        raise ValueError("code is invalid")


__all__ = ["CitizenReportConnector", "HttpCitizenReportConnector"]
