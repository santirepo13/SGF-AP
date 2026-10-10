"""Shared repository/service correspondence and stable method-case builders."""

from api import repositories, services
from api.interfaces import repositories as repository_interfaces
from api.interfaces import services as service_interfaces


_REPOSITORY_NAMES = ["Municipality","Commune","Neighborhood","RoadType","RoadSuffixLetter","RoadBisCode","RoadQuadrant","CrossSuffixLetter","CrossBisCode","CrossQuadrant","Address","Role","User","Crew","CrewMember","Priority","FailureType","Status","Action","Ticket","Evidence","HistoryEvent"]
_SERVICE_NAMES = ["Catalog","Address","User","Crew","Ticket","Evidence","History"]

REPOSITORY_PAIRS = tuple(
    (getattr(repository_interfaces, name + "RepositoryInterface"),
     getattr(repositories, name + "Repository"))
    for name in _REPOSITORY_NAMES
)
SERVICE_PAIRS = tuple(
    (getattr(service_interfaces, name + "ServiceInterface"),
     getattr(services, name + "Service"))
    for name in _SERVICE_NAMES
)


def public_methods(interface):
    return tuple(name for name, declaration in interface.__dict__.items()
                 if not name.startswith("_") and callable(declaration))


def method_cases(pairs, prefix, variant, *, exclude_creates=False):
    methods = ((interface, implementation, method)
               for interface, implementation in pairs
               for method in public_methods(interface)
               if not exclude_creates or method != "create")
    return tuple((f"{prefix}-{index:02d}.{variant}", interface, implementation, method)
                 for index, (interface, implementation, method) in enumerate(methods, 1))
