from ..mapping import failure_type
from ..persistence import RepositoryBase
class FailureTypeRepository(RepositoryBase):
    def get_by_id(self, failure_type_id: int): return self.fetch_one("SELECT id, name, priority_id FROM failure_types WHERE id = %s", (failure_type_id,), operation="failure_types.get_by_id", entity="failure_type", mapper=failure_type)
    def list_all(self): return self.fetch_all("SELECT id, name, priority_id FROM failure_types ORDER BY id", (), operation="failure_types.list_all", entity="failure_type", mapper=failure_type)
    def list_by_priority(self, priority_id: int): return self.fetch_all("SELECT id, name, priority_id FROM failure_types WHERE priority_id = %s ORDER BY id", (priority_id,), operation="failure_types.list_by_priority", entity="failure_type", mapper=failure_type)
