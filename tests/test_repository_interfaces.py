import inspect

from api.interfaces.repositories import *
from api.repositories import (
    ActionRepository, AddressRepository, CommuneRepository, CrewMemberRepository,
    CrewRepository, CrossBisCodeRepository, CrossQuadrantRepository,
    CrossSuffixLetterRepository, EvidenceRepository, FailureTypeRepository,
    HistoryEventRepository, MunicipalityRepository, NeighborhoodRepository,
    PriorityRepository, RoadBisCodeRepository, RoadQuadrantRepository,
    RoadSuffixLetterRepository, RoadTypeRepository, RoleRepository,
    StatusRepository, TicketRepository, UserRepository,
)


PAIRS = {
    ActionRepositoryInterface: ActionRepository,
    AddressRepositoryInterface: AddressRepository,
    CommuneRepositoryInterface: CommuneRepository,
    CrewMemberRepositoryInterface: CrewMemberRepository,
    CrewRepositoryInterface: CrewRepository,
    CrossBisCodeRepositoryInterface: CrossBisCodeRepository,
    CrossQuadrantRepositoryInterface: CrossQuadrantRepository,
    CrossSuffixLetterRepositoryInterface: CrossSuffixLetterRepository,
    EvidenceRepositoryInterface: EvidenceRepository,
    FailureTypeRepositoryInterface: FailureTypeRepository,
    HistoryEventRepositoryInterface: HistoryEventRepository,
    MunicipalityRepositoryInterface: MunicipalityRepository,
    NeighborhoodRepositoryInterface: NeighborhoodRepository,
    PriorityRepositoryInterface: PriorityRepository,
    RoadBisCodeRepositoryInterface: RoadBisCodeRepository,
    RoadQuadrantRepositoryInterface: RoadQuadrantRepository,
    RoadSuffixLetterRepositoryInterface: RoadSuffixLetterRepository,
    RoadTypeRepositoryInterface: RoadTypeRepository,
    RoleRepositoryInterface: RoleRepository,
    StatusRepositoryInterface: StatusRepository,
    TicketRepositoryInterface: TicketRepository,
    UserRepositoryInterface: UserRepository,
}


def test_every_repository_implementation_matches_its_interface_methods():
    assert len(PAIRS) == 22
    for interface, implementation in PAIRS.items():
        for name, declaration in interface.__dict__.items():
            if name.startswith("_") or not callable(declaration):
                continue
            expected = list(inspect.signature(declaration).parameters)
            actual = list(inspect.signature(getattr(implementation, name)).parameters)
            assert actual == expected, f"{implementation.__name__}.{name} does not match"
