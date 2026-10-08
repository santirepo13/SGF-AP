"""Concrete persistence repositories for SGF-AP.

Repositories receive a DB-API-like connection and never commit or roll back.
"""

from .geolocation import CommuneRepository, MunicipalityRepository, NeighborhoodRepository
from .address import (AddressRepository, CrossBisCodeRepository, CrossQuadrantRepository, CrossSuffixLetterRepository, RoadBisCodeRepository, RoadQuadrantRepository, RoadSuffixLetterRepository, RoadTypeRepository)
from .tickets import ActionRepository, EvidenceRepository, FailureTypeRepository, HistoryEventRepository, PriorityRepository, StatusRepository, TicketFilters, TicketRepository
from .users import CrewMemberRepository, CrewRepository, RoleRepository, UserFilters, UserRepository
from .persistence import ConnectionProtocol, CursorProtocol, RepositoryBase

__all__ = [
    "ConnectionProtocol", "CursorProtocol", "RepositoryBase",
    "MunicipalityRepository", "CommuneRepository", "NeighborhoodRepository",
    "RoadTypeRepository", "RoadSuffixLetterRepository", "RoadBisCodeRepository",
    "RoadQuadrantRepository", "CrossSuffixLetterRepository", "CrossBisCodeRepository",
    "CrossQuadrantRepository", "AddressRepository", "RoleRepository", "UserRepository",
    "CrewRepository", "CrewMemberRepository", "PriorityRepository", "FailureTypeRepository",
    "StatusRepository", "ActionRepository", "TicketRepository", "TicketFilters",
    "EvidenceRepository", "HistoryEventRepository", "UserFilters",
]
