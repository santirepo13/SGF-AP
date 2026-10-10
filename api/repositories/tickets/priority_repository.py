from api.enums import PriorityName
from ..catalog_repository import IdNameCatalogRepository
from ..mapping import priority
class PriorityRepository(IdNameCatalogRepository):
    table, model, name_type = "priorities", priority, PriorityName
