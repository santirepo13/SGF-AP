"""Official Resend SDK adapter for password-recovery emails."""

from __future__ import annotations

from html import escape
import os
import re
from typing import Protocol

import resend
from resend.exceptions import ResendError


class PasswordRecoveryNotifier(Protocol):
    def send_code(self, *, recipient: str, request_id: str, code: str, expires_in_minutes: int) -> None: ...

    def send_password_changed(self, *, recipient: str, recovery_id: str) -> None: ...


class ResendNotificationError(RuntimeError):
    """Provider failure without message bodies, recipients, proofs, or secrets."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


class ResendPasswordRecoveryNotifier:
    """Send server-generated recovery messages through the official Resend SDK."""

    def __init__(self, *, api_key: str, from_email: str, timeout_seconds: int = 10) -> None:
        if type(api_key) is not str or not api_key:
            raise ValueError("Resend API key is required")
        if type(from_email) is not str or not from_email:
            raise ValueError("Resend sender is required")
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise ValueError("Resend timeout must be a positive integer")

        # The key originates in api/.env and is never included in a request,
        # response, exception reason, or log entry.
        os.environ["RESEND_API_KEY"] = api_key
        resend.api_key = os.environ["RESEND_API_KEY"]
        resend.default_http_client = resend.RequestsClient(timeout=timeout_seconds)
        self._from_email = from_email

    def send_code(self, *, recipient: str, request_id: str, code: str, expires_in_minutes: int) -> None:
        self._send(
            recipient=recipient,
            subject="SGF-AP: código para recuperar tu contraseña",
            text=(
                f"Tu código de recuperación de SGF-AP es: {code}\n\n"
                f"Escríbelo o pégalo en la aplicación. Vence en {expires_in_minutes} minutos.\n"
                "No compartas este código con nadie."
            ),
            html=(
                "<p>Tu código de recuperación de <strong>SGF-AP</strong> es:</p>"
                f"<p style=\"font-size:24px;letter-spacing:4px\"><strong>{escape(code)}</strong></p>"
                f"<p>Escríbelo o pégalo en la aplicación. Vence en {expires_in_minutes} minutos.</p>"
                "<p>No compartas este código con nadie.</p>"
            ),
            idempotency_key=f"password-recovery-code/{request_id}",
        )

    def send_password_changed(self, *, recipient: str, recovery_id: str) -> None:
        self._send(
            recipient=recipient,
            subject="SGF-AP: tu contraseña fue actualizada",
            text="La contraseña de tu cuenta SGF-AP fue actualizada. Debes ingresar nuevamente para continuar.",
            html=(
                "<p>La contraseña de tu cuenta <strong>SGF-AP</strong> fue actualizada.</p>"
                "<p>Debes ingresar nuevamente para continuar.</p>"
            ),
            idempotency_key=f"password-recovery-completed/{recovery_id}",
        )

    def _send(self, *, recipient: str, subject: str, text: str, html: str, idempotency_key: str) -> None:
        params: resend.Emails.SendParams = {
            "from": self._from_email,
            "to": [recipient],
            "subject": subject,
            "text": text,
            "html": html,
        }
        options: resend.Emails.SendOptions = {"idempotency_key": idempotency_key}
        try:
            resend.Emails.send(params, options)
        except ResendError as error:
            raise ResendNotificationError(
                "email provider rejected the request",
                status_code=_status_code(error),
                reason=_safe_provider_reason(error),
            ) from error
        except ValueError as error:
            raise ResendNotificationError(
                "email provider request is invalid",
                reason="invalid Resend email parameters",
            ) from error


def _status_code(error: ResendError) -> int | None:
    try:
        status_code = int(error.code)
    except (TypeError, ValueError):
        return None
    return status_code if 100 <= status_code <= 599 else None


def _safe_provider_reason(error: ResendError) -> str:
    """Keep only a short, redacted SDK diagnostic in server logs."""

    error_type = getattr(error, "error_type", "resend_error")
    message = getattr(error, "message", str(error))
    value = f"{error_type}: {message}"
    value = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted-email>", value)
    value = re.sub(r"\bre_[A-Za-z0-9_-]+\b", "<redacted-api-key>", value)
    return " ".join(value.split())[:240] or "resend request failed"


__all__ = ["PasswordRecoveryNotifier", "ResendNotificationError", "ResendPasswordRecoveryNotifier"]
