"""Executable inventory checks for the Scrum 1–9 test matrix."""

import inspect

import pytest

from api.interfaces.repositories import *
from api.interfaces.services import *
from api.repositories import *
from api.services import *
from tests.case_registry import build_cases


REPOSITORY_PAIRS = [
    (MunicipalityRepositoryInterface, MunicipalityRepository),
    (CommuneRepositoryInterface, CommuneRepository),
    (NeighborhoodRepositoryInterface, NeighborhoodRepository),
    (RoadTypeRepositoryInterface, RoadTypeRepository),
    (RoadSuffixLetterRepositoryInterface, RoadSuffixLetterRepository),
    (RoadBisCodeRepositoryInterface, RoadBisCodeRepository),
    (RoadQuadrantRepositoryInterface, RoadQuadrantRepository),
    (CrossSuffixLetterRepositoryInterface, CrossSuffixLetterRepository),
    (CrossBisCodeRepositoryInterface, CrossBisCodeRepository),
    (CrossQuadrantRepositoryInterface, CrossQuadrantRepository),
    (AddressRepositoryInterface, AddressRepository),
    (RoleRepositoryInterface, RoleRepository),
    (UserRepositoryInterface, UserRepository),
    (CrewRepositoryInterface, CrewRepository),
    (CrewMemberRepositoryInterface, CrewMemberRepository),
    (PriorityRepositoryInterface, PriorityRepository),
    (FailureTypeRepositoryInterface, FailureTypeRepository),
    (StatusRepositoryInterface, StatusRepository),
    (ActionRepositoryInterface, ActionRepository),
    (TicketRepositoryInterface, TicketRepository),
    (EvidenceRepositoryInterface, EvidenceRepository),
    (HistoryEventRepositoryInterface, HistoryEventRepository),
]

SERVICE_PAIRS = [
    (CatalogServiceInterface, CatalogService),
    (AddressServiceInterface, AddressService),
    (UserServiceInterface, UserService),
    (CrewServiceInterface, CrewService),
    (TicketServiceInterface, TicketService),
    (EvidenceServiceInterface, EvidenceService),
    (HistoryServiceInterface, HistoryService),
]


def public_methods(interface):
    return tuple(
        name for name, declaration in interface.__dict__.items()
        if not name.startswith("_") and callable(declaration)
    )


def test_repository_inventory_contains_22_interfaces_and_70_methods():
    assert len(REPOSITORY_PAIRS) == 22
    assert sum(len(public_methods(interface)) for interface, _ in REPOSITORY_PAIRS) == 70


def test_service_inventory_contains_7_interfaces_and_55_methods():
    assert len(SERVICE_PAIRS) == 7
    assert sum(len(public_methods(interface)) for interface, _ in SERVICE_PAIRS) == 55


REPOSITORY_METHOD_CASES = tuple(
    (f"R4-{index:02d}", interface, implementation, method)
    for index, (interface, implementation, method) in enumerate(
        ((interface, implementation, method)
         for interface, implementation in REPOSITORY_PAIRS
         for method in public_methods(interface)), 1
    )
)

SERVICE_METHOD_CASES = tuple(
    (f"S6-{index:02d}", interface, implementation, method)
    for index, (interface, implementation, method) in enumerate(
        ((interface, implementation, method)
         for interface, implementation in SERVICE_PAIRS
         for method in public_methods(interface)), 1
    )
)


@pytest.mark.parametrize("case_id, interface, implementation, method", REPOSITORY_METHOD_CASES, ids=[case[0] for case in REPOSITORY_METHOD_CASES])
def test_each_repository_method_is_executable_through_its_pair(case_id, interface, implementation, method):
    assert hasattr(implementation, method), f"{case_id}: missing repository method {implementation.__name__}.{method}"
    expected = inspect.signature(getattr(interface, method)).parameters
    actual = inspect.signature(getattr(implementation, method)).parameters
    assert list(actual) == list(expected), f"{case_id}: incompatible repository signature"


@pytest.mark.parametrize("case_id, interface, implementation, method", SERVICE_METHOD_CASES, ids=[case[0] for case in SERVICE_METHOD_CASES])
def test_each_service_method_is_executable_through_its_pair(case_id, interface, implementation, method):
    assert hasattr(implementation, method), f"{case_id}: missing service method {implementation.__name__}.{method}"
    expected = inspect.signature(getattr(interface, method)).parameters
    actual = inspect.signature(getattr(implementation, method)).parameters
    assert list(actual) == list(expected), f"{case_id}: incompatible service signature"


def test_case_registry_rejects_duplicate_ids_and_preserves_traceability():
    cases = build_cases((
        ("S1-A01", "S1", "active default", "dto", "omitted", "True", __file__),
        ("S8-22", "S8", "single invocation", "double", "valid", "one call", __file__),
    ))
    assert [case.case_id for case in cases] == ["S1-A01", "S8-22"]
    assert all(case.test_file for case in cases)
    with pytest.raises(ValueError):
        build_cases((
            ("DUP", "S1", "r", "p", "i", "e", __file__),
            ("DUP", "S1", "r", "p", "i", "e", __file__),
        ))
