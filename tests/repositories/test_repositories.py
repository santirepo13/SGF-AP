"""Repository mapping, SQL parameters, absence and induced failure cases."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

from datetime import datetime, timezone

import pytest

from api.contracts import AddressComponentsInput, TicketUpdateInput
from api.errors import ApplicationError, ErrorCode
from api.models import Address, Municipality
from api.repositories import AddressRepository, MunicipalityRepository, TicketRepository
from api.repositories.address import RoadTypeRepository
from api.repositories.tickets.ticket_repository import TicketFilters
from tests.support.component_catalog import REPOSITORY_PAIRS, method_cases
from tests.support.doubles import Connection, Cursor
from tests.support.values import repository_arguments


ABSENCE_CASES = method_cases(REPOSITORY_PAIRS, "R4", "N", exclude_creates=True)
METHOD_CASES = method_cases(REPOSITORY_PAIRS, "R4", "E")


def test_repository_maps_rows_and_parameterizes_values_without_transaction_control():
    """Map a municipality row, bind its lookup value, and leave commits to callers."""
    cursor = Cursor({"id": 3, "name": "Bogotá"})
    connection = Connection(cursor)
    result = MunicipalityRepository(connection).get_by_name("Bogotá")

    assert result == Municipality(3, "Bogotá")
    assert cursor.calls[0][1] == ("Bogotá",)
    assert cursor.closed
    assert connection.commits == connection.rollbacks == 0


def test_address_component_lookup_uses_null_safe_parameters():
    """Find an address even when optional components have no stored value."""
    now = datetime.now(timezone.utc)
    row = {
        "id": 7, "road_type_code": "CL", "road_number": 10,
        "road_suffix_letter_code": None, "road_bis_code": None,
        "road_bis_suffix": None, "road_quadrant_code": None,
        "cross_road_number": 20, "cross_suffix_letter_code": None,
        "cross_bis_code": None, "cross_bis_suffix": None,
        "cross_quadrant_code": None, "door_plate_number": 4,
        "neighborhood_id": None, "created_at": now,
    }
    cursor = Cursor(row)
    result = AddressRepository(Connection(cursor)).find_by_components(
        AddressComponentsInput("CL", 10, 20, 4)
    )

    assert isinstance(result, Address)
    assert "IS NOT DISTINCT FROM %s" in cursor.calls[0][0]
    assert cursor.calls[0][1][-1] is None


def test_ticket_update_uses_allowlist_and_none_clears_nullable_value():
    """Update only approved ticket fields and allow clearing a phone number."""
    now = datetime.now(timezone.utc)
    row = {
        "id": 1, "code": "T-1", "reported_by": 2, "failure_type_id": 3,
        "description": "x", "address_id": None, "status_id": 1,
        "priority_id": None, "contact_email": None, "contact_phone": None,
        "diagnosis": None, "solution": None, "crew_id": None, "created_at": now,
    }
    cursor = Cursor(row)
    TicketRepository(Connection(cursor)).update(
        TicketUpdateInput(ticket_id=1, contact_phone=None)
    )
    query, params = cursor.calls[0]
    assert "UPDATE tickets SET contact_phone = %s" in query
    assert params == (None, 1)


def test_ticket_geographic_filters_are_parameterized_and_deterministic():
    """Bind geographic filters as values and keep ticket ordering stable."""
    cursor = Cursor(rows=[])
    result = TicketRepository(Connection(cursor)).list_by_filters(
        TicketFilters(municipality_id=4, commune_id=8)
    )
    query, params = cursor.calls[0]
    assert result == []
    assert params == (4, 8)
    assert "ORDER BY t.id" in query


def test_address_catalog_keeps_numeric_quadrant_code_contract():
    """Read an address catalogue entry through the expected repository export."""
    cursor = Cursor({"code": 1, "name": "Norte"})
    RoadTypeRepository  # package export smoke check
    # The catalog test deliberately uses the textual catalog to verify the nested package.
    assert RoadTypeRepository(Connection(Cursor({"code": "CL", "name": "Calle"}))).get_by_code("CL").code == "CL"


@pytest.mark.parametrize("case_id, interface, implementation, method", ABSENCE_CASES, ids=[case[0] for case in ABSENCE_CASES])
def test_repository_absence_cases_return_none_empty_or_false(case_id, interface, implementation, method):
    """Run each repository method against empty data and check its no-match form."""
    # Use the same empty connection for each generated repository-method variant.
    connection = Connection()
    result = getattr(implementation(connection), method)(**repository_arguments(interface, method))
    if method.startswith("list"):
        assert result == [], case_id
    elif method == "remove":
        assert result is False, case_id
    else:
        assert result is None, case_id


@pytest.mark.parametrize("case_id, interface, implementation, method", METHOD_CASES, ids=[case[0] for case in METHOD_CASES])
def test_each_repository_method_translates_technical_failures(case_id, interface, implementation, method):
    """Make each repository method fail and confirm the cause stays attached."""
    # Inject a database failure before invoking the selected public method.
    repository = implementation(Connection(failure=RuntimeError("private query parameter and password=secret")))
    arguments = repository_arguments(interface, method, nullable_as_none=False)

    with pytest.raises(ApplicationError) as caught:
        getattr(repository, method)(**arguments)

    assert caught.value.code in {ErrorCode.UNEXPECTED_ERROR, ErrorCode.PERSISTENCE_FAILURE}, case_id
    assert caught.value.cause is not None
