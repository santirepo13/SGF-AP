"""Safe citizen-query contracts, projections and cursor checks."""

from datetime import datetime, timezone

import pytest

from api.contracts import (
    CitizenHistoryItem,
    CitizenQueryPageInput,
    CitizenTicketCodeInput,
    CitizenTicketListItem,
    PublicTicketOutput,
)
from api.services.tickets.citizen_projections import (
    CitizenCursorCodec,
    CitizenCursorError,
    action_projection,
    status_projection,
)


def test_citizen_contracts_require_aware_dates_and_valid_page_limits() -> None:
    now = datetime.now(timezone.utc)
    CitizenTicketListItem("SGF-1", now, "Registered", "Registrado", "Luz apagada", now)
    PublicTicketOutput("SGF-1", "Registered", "Registrado", now, "Recibido")
    CitizenHistoryItem(now, "Registration", "Reporte registrado")
    with pytest.raises(ValueError):
        CitizenTicketListItem("SGF-1", now.replace(tzinfo=None), "Registered", "Registrado", "Luz apagada", now)
    with pytest.raises(ValueError):
        CitizenQueryPageInput(limit=51)
    with pytest.raises(ValueError):
        CitizenTicketCodeInput(" ")
    with pytest.raises(ValueError):
        CitizenQueryPageInput(cursor="x" * 513)


@pytest.mark.parametrize(
    ("persisted", "expected"),
    [
        ("PendingClosure", ("PendingClosure", "Pendiente de cierre")),
        ("Resolved", ("Resolved", "Resuelto")),
        ("unknown-internal-status", ("Unavailable", "Estado no disponible")),
    ],
)
def test_status_projection_never_exposes_unknown_status(persisted, expected) -> None:
    projected = status_projection(persisted)
    assert projected[:2] == expected
    if expected[0] == "Unavailable":
        assert "unknown-internal-status" not in " ".join(projected)


def test_rejection_history_is_presented_as_continuing_attention() -> None:
    assert action_projection("Rejection") == (
        "Rejection",
        "El reporte continúa en atención",
    )
    assert action_projection("unknown-action") == (
        "Unavailable",
        "Actualización no disponible",
    )


def test_cursor_is_signed_and_bound_to_account_or_ticket() -> None:
    codec = CitizenCursorCodec(b"c" * 32)
    token = codec.encode("reports", "account-7", datetime.now(timezone.utc), "SGF-7")
    assert codec.decode(token, "reports", "account-7")[1] == "SGF-7"
    with pytest.raises(CitizenCursorError):
        codec.decode(token, "reports", "account-8")
    tampered = ("A" if token[0] != "A" else "B") + token[1:]
    with pytest.raises(CitizenCursorError):
        codec.decode(tampered, "reports", "account-7")
    with pytest.raises(CitizenCursorError):
        codec.decode(token, "history", "ticket-7")
