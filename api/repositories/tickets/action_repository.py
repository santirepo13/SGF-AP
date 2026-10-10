from api.enums import ActionName
from ..catalog_repository import IdNameCatalogRepository
from ..mapping import action
class ActionRepository(IdNameCatalogRepository):
    table, model, name_type = "actions", action, ActionName
