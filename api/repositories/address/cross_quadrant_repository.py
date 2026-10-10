from api.models.address.addresses import CrossQuadrant
from ..catalog_repository import CodeCatalogRepository
from ..mapping import cross_quadrant
class CrossQuadrantRepository(CodeCatalogRepository[CrossQuadrant]):
    table, model, code_type = "cross_quadrants", cross_quadrant, int
