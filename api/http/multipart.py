"""Bounded parsing of a single evidence multipart request."""

from __future__ import annotations

from datetime import datetime
from email.message import Message


from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from api.contracts import EvidenceUploadInput
from api.errors import ApplicationError, ErrorCode


async def read_single_evidence_multipart(request, *, correlation_id: str):
    config = request.app.state.api_config.evidence_storage
    header = request.headers.get("content-type", "")
    content_type = Message()
    content_type["content-type"] = header
    boundary = content_type.get_param("boundary")
    if content_type.get_content_type().lower() != "multipart/form-data" or not boundary:
        raise ApplicationError.invalid_value(
            None, "Se requiere multipart/form-data con boundary.", correlation_id=correlation_id,
        )

    total = 0
    maximum = config.max_file_bytes + config.multipart_envelope_max_bytes
    exceeded = False

    async def limited_stream():
        nonlocal total, exceeded
        async for chunk in request.stream():
            total += len(chunk)
            if total > maximum:
                exceeded = True
                raise MultiPartException("multipart request is too large")
            yield chunk

    parser = MultiPartParser(request.headers, limited_stream(), max_files=1, max_fields=4)
    try:
        form = await parser.parse()
    except MultiPartException as error:
        if exceeded:
            raise ApplicationError.with_code(
                ErrorCode.EVIDENCE_TOO_LARGE, correlation_id=correlation_id, cause=error,
            ) from error
        raise ApplicationError.invalid_value(
            None, "El formulario multipart no es válido.", correlation_id=correlation_id, cause=error,
        ) from error

    try:
        parts = form.multi_items()
        names = [name for name, _ in parts]
        required = {"file", "request_key", "upload_key", "capture_source"}
        if len(names) != len(set(names)) or not required <= set(names) or set(names) - (required | {"captured_at"}):
            raise ApplicationError.invalid_value(
                None, "Los campos del formulario no son válidos.", correlation_id=correlation_id,
            )
        values = dict(parts)
        file = values["file"]
        if not isinstance(file, UploadFile) or any(
            not isinstance(values[name], str) for name in required - {"file"}
        ) or ("captured_at" in values and not isinstance(values["captured_at"], str)):
            raise ApplicationError.invalid_value(
                None, "Los tipos de los campos multipart no son válidos.", correlation_id=correlation_id,
            )
        if file.size is None or file.size > config.max_file_bytes:
            raise ApplicationError.with_code(ErrorCode.EVIDENCE_TOO_LARGE, correlation_id=correlation_id)
        if total - file.size > config.multipart_envelope_max_bytes:
            raise ApplicationError.with_code(ErrorCode.EVIDENCE_TOO_LARGE, correlation_id=correlation_id)
        raw_time = values.get("captured_at")
        captured_at = None
        if raw_time is not None:
            try:
                captured_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                if captured_at.tzinfo is None or captured_at.utcoffset() is None:
                    raise ValueError("timezone required")
            except ValueError as error:
                raise ApplicationError.invalid_value(
                    "captured_at", "La fecha debe incluir zona horaria.",
                    correlation_id=correlation_id, cause=error,
                ) from error
        await file.seek(0)
        return EvidenceUploadInput(
            request_key=values["request_key"], upload_key=values["upload_key"],
            capture_source=values["capture_source"], captured_at=captured_at, content=file.file,
        )
    except BaseException:
        await form.close()
        raise