from api.models import Municipality
from ..mapping import municipality
from ..persistence import RepositoryBase

class MunicipalityRepository(RepositoryBase):
    def get_by_id(self, municipality_id: int):
        return self.fetch_one("SELECT id, name FROM municipalities WHERE id = %s", (municipality_id,), operation="municipalities.get_by_id", entity="municipality", mapper=municipality)
    def get_by_name(self, name: str):
        return self.fetch_one("SELECT id, name FROM municipalities WHERE name = %s", (name,), operation="municipalities.get_by_name", entity="municipality", mapper=municipality)
    def list_all(self):
        return self.fetch_all("SELECT id, name FROM municipalities ORDER BY id", (), operation="municipalities.list_all", entity="municipality", mapper=municipality)
