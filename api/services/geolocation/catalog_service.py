"""Typed catalog and geographic lookups."""

from api.contracts import *
from api.interfaces.repositories import *
from api.models import *
from ..base import ServiceBase


class CatalogService(ServiceBase):
    def __init__(self, municipalities: MunicipalityRepositoryInterface, communes: CommuneRepositoryInterface, neighborhoods: NeighborhoodRepositoryInterface, road_types: RoadTypeRepositoryInterface, road_suffix_letters: RoadSuffixLetterRepositoryInterface, road_bis_codes: RoadBisCodeRepositoryInterface, road_quadrants: RoadQuadrantRepositoryInterface, cross_suffix_letters: CrossSuffixLetterRepositoryInterface, cross_bis_codes: CrossBisCodeRepositoryInterface, cross_quadrants: CrossQuadrantRepositoryInterface, roles: RoleRepositoryInterface, priorities: PriorityRepositoryInterface, failure_types: FailureTypeRepositoryInterface, statuses: StatusRepositoryInterface, actions: ActionRepositoryInterface, **kwargs):
        super().__init__(**kwargs)
        self.municipalities, self.communes, self.neighborhoods = municipalities, communes, neighborhoods
        self.road_types, self.road_suffix_letters, self.road_bis_codes, self.road_quadrants = road_types, road_suffix_letters, road_bis_codes, road_quadrants
        self.cross_suffix_letters, self.cross_bis_codes, self.cross_quadrants = cross_suffix_letters, cross_bis_codes, cross_quadrants
        self.roles, self.priorities, self.failure_types, self.statuses, self.actions = roles, priorities, failure_types, statuses, actions

    def _list(self, context, repo, method, output, *args) -> OperationResult[list]:
        return self._execute(context, context.operation, lambda: [output(**vars(item)) for item in getattr(repo, method)(*args)])
    def list_municipalities(self, context) -> OperationResult[list[MunicipalityOutput]]: return self._list(context, self.municipalities, "list_all", MunicipalityOutput)
    def list_communes(self, context, municipality_id: int) -> OperationResult[list[CommuneOutput]]: return self._list(context, self.communes, "list_by_municipality", CommuneOutput, municipality_id)
    def list_neighborhoods_by_municipality(self, context, municipality_id: int) -> OperationResult[list[NeighborhoodOutput]]: return self._list(context, self.neighborhoods, "list_by_municipality", NeighborhoodOutput, municipality_id)
    def list_neighborhoods_by_commune(self, context, commune_id: int) -> OperationResult[list[NeighborhoodOutput]]: return self._list(context, self.neighborhoods, "list_by_commune", NeighborhoodOutput, commune_id)
    def list_neighborhoods_without_commune(self, context, municipality_id: int) -> OperationResult[list[NeighborhoodOutput]]: return self._list(context, self.neighborhoods, "list_without_commune", NeighborhoodOutput, municipality_id)
    def list_road_types(self, context) -> OperationResult[list[RoadTypeOutput]]: return self._list(context, self.road_types, "list_all", RoadTypeOutput)
    def list_road_suffix_letters(self, context) -> OperationResult[list[RoadSuffixLetterOutput]]: return self._list(context, self.road_suffix_letters, "list_all", RoadSuffixLetterOutput)
    def list_road_bis_codes(self, context) -> OperationResult[list[RoadBisCodeOutput]]: return self._list(context, self.road_bis_codes, "list_all", RoadBisCodeOutput)
    def list_road_quadrants(self, context) -> OperationResult[list[RoadQuadrantOutput]]: return self._list(context, self.road_quadrants, "list_all", RoadQuadrantOutput)
    def list_cross_suffix_letters(self, context) -> OperationResult[list[CrossSuffixLetterOutput]]: return self._list(context, self.cross_suffix_letters, "list_all", CrossSuffixLetterOutput)
    def list_cross_bis_codes(self, context) -> OperationResult[list[CrossBisCodeOutput]]: return self._list(context, self.cross_bis_codes, "list_all", CrossBisCodeOutput)
    def list_cross_quadrants(self, context) -> OperationResult[list[CrossQuadrantOutput]]: return self._list(context, self.cross_quadrants, "list_all", CrossQuadrantOutput)
    def list_roles(self, context) -> OperationResult[list[RoleOutput]]: return self._list(context, self.roles, "list_all", RoleOutput)
    def list_priorities(self, context) -> OperationResult[list[PriorityOutput]]: return self._list(context, self.priorities, "list_all", PriorityOutput)
    def list_failure_types(self, context) -> OperationResult[list[FailureTypeOutput]]: return self._list(context, self.failure_types, "list_all", FailureTypeOutput)
    def list_failure_types_by_priority(self, context, priority_id: int) -> OperationResult[list[FailureTypeOutput]]: return self._list(context, self.failure_types, "list_by_priority", FailureTypeOutput, priority_id)
    def list_statuses(self, context) -> OperationResult[list[StatusOutput]]: return self._list(context, self.statuses, "list_all", StatusOutput)
    def list_actions(self, context) -> OperationResult[list[ActionOutput]]: return self._list(context, self.actions, "list_all", ActionOutput)
