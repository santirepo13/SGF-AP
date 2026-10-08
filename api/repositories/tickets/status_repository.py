from api.enums import StatusName
from ..catalog_repository import IdNameCatalogRepository
from ..mapping import status
class StatusRepository(IdNameCatalogRepository):
    table, model, name_type = "statuses", status, StatusName
