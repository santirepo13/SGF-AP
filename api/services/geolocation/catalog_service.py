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

    def _list(self, context, repo, method, output, *args):
        return self._execute(context, context.operation, lambda: [output(**vars(item)) for item in getattr(repo, method)(*args)])
    def listar_municipios(self, context): return self._list(context, self.municipalities, "list_all", MunicipalityOutput)
    def listar_comunas(self, context, municipality_id: int): return self._list(context, self.communes, "list_by_municipality", CommuneOutput, municipality_id)
    def listar_barrios_por_municipio(self, context, municipality_id: int): return self._list(context, self.neighborhoods, "list_by_municipality", NeighborhoodOutput, municipality_id)
    def listar_barrios_por_comuna(self, context, commune_id: int): return self._list(context, self.neighborhoods, "list_by_commune", NeighborhoodOutput, commune_id)
    def listar_barrios_sin_comuna(self, context, municipality_id: int): return self._list(context, self.neighborhoods, "list_without_commune", NeighborhoodOutput, municipality_id)
    def listar_tipos_via(self, context): return self._list(context, self.road_types, "list_all", RoadTypeOutput)
    def listar_sufijos_via(self, context): return self._list(context, self.road_suffix_letters, "list_all", RoadSuffixLetterOutput)
    def listar_codigos_bis_via(self, context): return self._list(context, self.road_bis_codes, "list_all", RoadBisCodeOutput)
    def listar_cuadrantes_via(self, context): return self._list(context, self.road_quadrants, "list_all", RoadQuadrantOutput)
    def listar_sufijos_cruce(self, context): return self._list(context, self.cross_suffix_letters, "list_all", CrossSuffixLetterOutput)
    def listar_codigos_bis_cruce(self, context): return self._list(context, self.cross_bis_codes, "list_all", CrossBisCodeOutput)
    def listar_cuadrantes_cruce(self, context): return self._list(context, self.cross_quadrants, "list_all", CrossQuadrantOutput)
    def listar_roles(self, context): return self._list(context, self.roles, "list_all", RoleOutput,)
    def listar_prioridades(self, context): return self._list(context, self.priorities, "list_all", PriorityOutput)
    def listar_tipos_falla(self, context): return self._list(context, self.failure_types, "list_all", FailureTypeOutput)
    def listar_tipos_falla_por_prioridad(self, context, priority_id: int): return self._list(context, self.failure_types, "list_by_priority", FailureTypeOutput, priority_id)
    def listar_estados(self, context): return self._list(context, self.statuses, "list_all", StatusOutput)
    def listar_acciones(self, context): return self._list(context, self.actions, "list_all", ActionOutput)
