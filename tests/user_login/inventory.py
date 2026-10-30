"""Login test inventory mapped to SGFAP-271 through SGFAP-281."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginCase:
    case_id: str
    subtask: str
    criterion: str
    automated_test: str | None
    modality: str = "automated"


LOGIN_CASES = (
    LoginCase("LOGIN-001", "ST2.1", "Campos obligatorios y correo válido", "test_login_contract.py"),
    LoginCase("LOGIN-002", "ST2.1", "Un intento en curso impide envíos duplicados", "test_login_client.py"),
    LoginCase("LOGIN-003", "ST2.2", "Contrato de entrada y salida sin datos sensibles", "test_login_contract.py"),
    LoginCase("LOGIN-004", "ST2.3", "Argon2id distingue rechazo y fallo interno", "test_password_verification.py"),
    LoginCase("LOGIN-005", "ST2.4", "Credenciales, activación, roles y emisión", "test_login_service.py"),
    LoginCase("LOGIN-006", "ST2.5", "JWT firmado, vigente y con propósito access", "test_access_tokens.py"),
    LoginCase("LOGIN-007", "ST2.6", "Actor actual desde token y políticas", "test_login_identity.py"),
    LoginCase("LOGIN-008", "ST2.7", "Ruta HTTP, sobre común y no-store", "test_login_http.py"),
    LoginCase("LOGIN-009", "ST2.8", "Errores de conexión y respuesta incompleta", "test_login_client.py"),
    LoginCase("LOGIN-010", "ST2.9", "Estado en memoria y destino por rol", "test_login_client.py"),
    LoginCase("LOGIN-011", "ST2.10", "Trazabilidad de criterios de aceptación", None, modality="manual"),
)


__all__ = ["LOGIN_CASES", "LoginCase"]
