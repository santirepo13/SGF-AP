from api.models.address.addresses import RoadSuffixLetter
from ..catalog_repository import CodeOnlyCatalogRepository
from ..mapping import road_suffix_letter
class RoadSuffixLetterRepository(CodeOnlyCatalogRepository[RoadSuffixLetter]):
    table, model, code_type = "road_suffix_letters", road_suffix_letter, str
