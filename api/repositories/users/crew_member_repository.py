from api.contracts import CrewMemberInput
from ..mapping import crew_member
from ..persistence import RepositoryBase
class CrewMemberRepository(RepositoryBase):
    def get_by_user_id(self, user_id: int): return self.fetch_one("SELECT user_id, crew_id FROM crew_members WHERE user_id = %s", (user_id,), operation="crew_members.get_by_user_id", entity="crew_member", mapper=crew_member)
    def list_by_crew(self, crew_id: int): return self.fetch_all("SELECT user_id, crew_id FROM crew_members WHERE crew_id = %s ORDER BY user_id", (crew_id,), operation="crew_members.list_by_crew", entity="crew_member", mapper=crew_member)
    def create(self, data: CrewMemberInput): return self.execute_one("INSERT INTO crew_members (user_id, crew_id) VALUES (%s, %s) RETURNING user_id, crew_id", (data.user_id, data.crew_id), operation="crew_members.create", entity="crew_member", mapper=crew_member)
    def update_crew(self, user_id: int, crew_id: int): return self.execute_one("UPDATE crew_members SET crew_id = %s WHERE user_id = %s RETURNING user_id, crew_id", (crew_id, user_id), operation="crew_members.update_crew", entity="crew_member", mapper=crew_member)
    def remove(self, user_id: int) -> bool:
        row = self.execute_one("DELETE FROM crew_members WHERE user_id = %s RETURNING user_id", (user_id,), operation="crew_members.remove", entity="crew_member")
        return row is not None
