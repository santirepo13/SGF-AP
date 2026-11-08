"""Citizen report API operations built on the shared authenticated transport."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol
from urllib.parse import quote

from .transport import MultipartFile, RegistrationTransport


class CitizenReportConnector(Protocol):
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


__all__ = ["CitizenReportConnector", "HttpCitizenReportConnector"]
