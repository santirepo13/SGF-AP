from api.models.address.addresses import RoadBisCode
from ..catalog_repository import CodeOnlyCatalogRepository
from ..mapping import road_bis_code
class RoadBisCodeRepository(CodeOnlyCatalogRepository[RoadBisCode]):
    table, model, code_type = "road_bis_codes", road_bis_code, str
