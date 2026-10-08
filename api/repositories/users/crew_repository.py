from api.contracts import CrewCreateInput, CrewUpdateInput
from ..mapping import crew
from ..persistence import RepositoryBase
class CrewRepository(RepositoryBase):
    def get_by_id(self, crew_id: int): return self.fetch_one("SELECT id, name FROM crews WHERE id = %s", (crew_id,), operation="crews.get_by_id", entity="crew", mapper=crew)
    def list_all(self): return self.fetch_all("SELECT id, name FROM crews ORDER BY id", (), operation="crews.list_all", entity="crew", mapper=crew)
    def create(self, data: CrewCreateInput): return self.execute_one("INSERT INTO crews (name) VALUES (%s) RETURNING id, name", (data.name,), operation="crews.create", entity="crew", mapper=crew)
    def update(self, data: CrewUpdateInput): return self.execute_one("UPDATE crews SET name = %s WHERE id = %s RETURNING id, name", (data.name, data.crew_id), operation="crews.update", entity="crew", mapper=crew)
