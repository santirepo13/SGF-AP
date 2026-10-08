from api.models.address.addresses import CrossSuffixLetter
from ..catalog_repository import CodeOnlyCatalogRepository
from ..mapping import cross_suffix_letter
class CrossSuffixLetterRepository(CodeOnlyCatalogRepository[CrossSuffixLetter]):
    table, model, code_type = "cross_suffix_letters", cross_suffix_letter, str
