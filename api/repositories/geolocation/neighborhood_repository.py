from ..mapping import neighborhood
from ..persistence import RepositoryBase

class NeighborhoodRepository(RepositoryBase):
    def get_by_id(self, neighborhood_id: int):
        return self.fetch_one("SELECT id, name, municipality_id, commune_id FROM neighborhoods WHERE id = %s", (neighborhood_id,), operation="neighborhoods.get_by_id", entity="neighborhood", mapper=neighborhood)
    def list_by_municipality(self, municipality_id: int):
        return self.fetch_all("SELECT id, name, municipality_id, commune_id FROM neighborhoods WHERE municipality_id = %s ORDER BY name, id", (municipality_id,), operation="neighborhoods.list_by_municipality", entity="neighborhood", mapper=neighborhood)
    def list_by_commune(self, commune_id: int):
        return self.fetch_all("SELECT id, name, municipality_id, commune_id FROM neighborhoods WHERE commune_id = %s ORDER BY name, id", (commune_id,), operation="neighborhoods.list_by_commune", entity="neighborhood", mapper=neighborhood)
    def list_without_commune(self, municipality_id: int):
        return self.fetch_all("SELECT id, name, municipality_id, commune_id FROM neighborhoods WHERE municipality_id = %s AND commune_id IS NULL ORDER BY name, id", (municipality_id,), operation="neighborhoods.list_without_commune", entity="neighborhood", mapper=neighborhood)
