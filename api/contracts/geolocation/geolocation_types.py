"""Geolocation outputs and lookup inputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MunicipalityOutput:
    id: int
    name: str


@dataclass(frozen=True)
class CommuneOutput:
    id: int
    number: int
    name: str | None
    municipality_id: int


@dataclass(frozen=True)
class NeighborhoodOutput:
    id: int
    name: str
    municipality_id: int
    commune_id: int | None


@dataclass(frozen=True)
class MunicipalityLookupInput:
    municipality_id: int


@dataclass(frozen=True)
class CommuneLookupInput:
    municipality_id: int


@dataclass(frozen=True)
class CommuneByIdInput:
    commune_id: int


@dataclass(frozen=True)
class NeighborhoodLookupInput:
    municipality_id: int
    commune_id: int | None = None


@dataclass(frozen=True)
class NeighborhoodByIdInput:
    neighborhood_id: int
