from api.models.address.addresses import CrossBisCode
from ..catalog_repository import CodeOnlyCatalogRepository
from ..mapping import cross_bis_code
class CrossBisCodeRepository(CodeOnlyCatalogRepository[CrossBisCode]):
    table, model, code_type = "cross_bis_codes", cross_bis_code, str
