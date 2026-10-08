from api.enums import RoleName
from ..catalog_repository import IdNameCatalogRepository
from ..mapping import role
class RoleRepository(IdNameCatalogRepository):
    table, model, name_type = "roles", role, RoleName
