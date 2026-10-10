from api.models.address.addresses import RoadType
from ..catalog_repository import CodeCatalogRepository
from ..mapping import road_type
class RoadTypeRepository(CodeCatalogRepository[RoadType]):
    table, model, code_type = "road_types", road_type, str
