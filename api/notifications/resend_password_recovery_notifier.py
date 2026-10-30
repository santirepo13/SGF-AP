"""Minimal Resend delivery adapter for password-recovery emails."""

from __future__ import annotations

from html import escape
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PasswordRecoveryNotifier(Protocol):
    def send_code(self, *, recipient: str, request_id: str, code: str, expires_in_minutes: int) -> None: ...

    def send_password_changed(self, *, recipient: str, recovery_id: str) -> None: ...


class ResendNotificationError(RuntimeError):
    """Provider failure without request bodies, email addresses, or secrets."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ResendPasswordRecoveryNotifier:
    def __init__(self, *, api_key: str, from_email: str, timeout_seconds: int = 10) -> None:
        if not api_key or not from_email:
            raise ValueError("Resend configuration is incomplete")
        self._api_key = api_key
        self._from_email = from_email
        self._timeout_seconds = timeout_seconds

    def send_code(self, *, recipient: str, request_id: str, code: str, expires_in_minutes: int) -> None:
        subject = "SGF-AP: código para recuperar tu contraseña"
        text = (
            f"Tu código de recuperación de SGF-AP es: {code}\n\n"
            f"Escríbelo o pégalo en la aplicación. Vence en {expires_in_minutes} minutos.\n"
            "No compartas este código con nadie."
        )
        html = (
            "<p>Tu código de recuperación de <strong>SGF-AP</strong> es:</p>"
            f"<p style=\"font-size:24px;letter-spacing:4px\"><strong>{escape(code)}</strong></p>"
            f"<p>Escríbelo o pégalo en la aplicación. Vence en {expires_in_minutes} minutos.</p>"
            "<p>No compartas este código con nadie.</p>"
        )
        self._send(
            recipient=recipient,
            subject=subject,
            text=text,
            html=html,
            idempotency_key=f"password-recovery-code/{request_id}",
        )

    def send_password_changed(self, *, recipient: str, recovery_id: str) -> None:
        self._send(
            recipient=recipient,
            subject="SGF-AP: tu contraseña fue actualizada",
            text="La contraseña de tu cuenta SGF-AP fue actualizada. Debes ingresar nuevamente para continuar.",
            html="<p>La contraseña de tu cuenta <strong>SGF-AP</strong> fue actualizada.</p><p>Debes ingresar nuevamente para continuar.</p>",
            idempotency_key=f"password-recovery-completed/{recovery_id}",
        )

    def _send(self, *, recipient: str, subject: str, text: str, html: str, idempotency_key: str) -> None:
        payload = json.dumps(
            {"from": self._from_email, "to": [recipient], "subject": subject, "text": text, "html": html},
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            "https://api.resend.com/emails",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                if not 200 <= response.status < 300:
                    raise ResendNotificationError("email provider rejected the request")
        except HTTPError as error:
            raise ResendNotificationError("email provider rejected the request", status_code=error.code) from error
        except (URLError, OSError, TimeoutError) as error:
            raise ResendNotificationError("email provider is unavailable") from error


__all__ = ["PasswordRecoveryNotifier", "ResendNotificationError", "ResendPasswordRecoveryNotifier"]
