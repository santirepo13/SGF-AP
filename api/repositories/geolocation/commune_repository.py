from ..mapping import commune
from ..persistence import RepositoryBase

class CommuneRepository(RepositoryBase):
    def get_by_id(self, commune_id: int):
        return self.fetch_one("SELECT id, number, name, municipality_id FROM communes WHERE id = %s", (commune_id,), operation="communes.get_by_id", entity="commune", mapper=commune)
    def get_by_municipality_and_number(self, municipality_id: int, number: int):
        return self.fetch_one("SELECT id, number, name, municipality_id FROM communes WHERE municipality_id = %s AND number = %s", (municipality_id, number), operation="communes.get_by_municipality_and_number", entity="commune", mapper=commune)
    def list_by_municipality(self, municipality_id: int):
        return self.fetch_all("SELECT id, number, name, municipality_id FROM communes WHERE municipality_id = %s ORDER BY number, id", (municipality_id,), operation="communes.list_by_municipality", entity="commune", mapper=commune)
