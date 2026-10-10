import inspect

from api.interfaces.services import (
    AddressServiceInterface, CatalogServiceInterface, CrewServiceInterface,
    EvidenceServiceInterface, HistoryServiceInterface, TicketServiceInterface,
    UserServiceInterface,
)
from api.services import AddressService, CatalogService, CrewService, EvidenceService, HistoryService, TicketService, UserService


PAIRS = {
    CatalogServiceInterface: CatalogService,
    AddressServiceInterface: AddressService,
    UserServiceInterface: UserService,
    CrewServiceInterface: CrewService,
    TicketServiceInterface: TicketService,
    EvidenceServiceInterface: EvidenceService,
    HistoryServiceInterface: HistoryService,
}


def test_service_implementations_match_their_service_interfaces():
    assert len(PAIRS) == 7
    for interface, implementation in PAIRS.items():
        for name, declaration in interface.__dict__.items():
            if name.startswith("_") or not callable(declaration):
                continue
            assert hasattr(implementation, name)
            expected = list(inspect.signature(declaration).parameters)
            implementation_method = getattr(implementation, name)
            expected_signature = inspect.signature(declaration)
            actual_signature = inspect.signature(implementation_method)
            actual = list(actual_signature.parameters)
            assert actual == expected, f"{implementation.__name__}.{name} does not match"
            for parameter_name, expected_parameter in expected_signature.parameters.items():
                actual_parameter = actual_signature.parameters[parameter_name]
                assert actual_parameter.default == expected_parameter.default
            assert inspect.get_annotations(declaration, eval_str=True).get("return") == inspect.get_annotations(implementation_method, eval_str=True).get("return"), f"{implementation.__name__}.{name} return type does not match"
