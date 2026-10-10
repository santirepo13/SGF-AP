from api.models.address.addresses import RoadQuadrant
from ..catalog_repository import CodeCatalogRepository
from ..mapping import road_quadrant
class RoadQuadrantRepository(CodeCatalogRepository[RoadQuadrant]):
    table, model, code_type = "road_quadrants", road_quadrant, int
