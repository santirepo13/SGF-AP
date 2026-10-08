from api.contracts import CrewCreateInput, CrewMemberInput, CrewMemberOutput, CrewOutput, CrewUpdateInput, OperationResult
from api.interfaces.repositories import CrewMemberRepositoryInterface, CrewRepositoryInterface, UserRepositoryInterface
from ..base import ServiceBase

class CrewService(ServiceBase):
    def __init__(self, crews: CrewRepositoryInterface, members: CrewMemberRepositoryInterface, users: UserRepositoryInterface, **kwargs): super().__init__(**kwargs); self.crews, self.members, self.users = crews, members, users
    @staticmethod
    def _crew(x): return CrewOutput(x.id, x.name)
    @staticmethod
    def _member(x): return CrewMemberOutput(x.user_id, x.crew_id)
    def get_by_id(self, context, crew_id: int) -> OperationResult[CrewOutput]:
        def work():
            value = self.crews.get_by_id(crew_id)
            if value is None: raise self._missing("crew", context)
            return self._crew(value)
        return self._execute(context, context.operation, work)
    def list_all(self, context) -> OperationResult[list[CrewOutput]]: return self._execute(context, context.operation, lambda: [self._crew(x) for x in self.crews.list_all()])
    def create(self, context, data: CrewCreateInput) -> OperationResult[CrewOutput]: return self._execute(context, context.operation, lambda: self._crew(self.crews.create(data)), write=True, actor_required=True)
    def update(self, context, data: CrewUpdateInput) -> OperationResult[CrewOutput]: return self._execute(context, context.operation, lambda: self._crew(x) if (x := self.crews.update(data)) else None, write=True, actor_required=True)
    def get_membership(self, context, user_id: int) -> OperationResult[CrewMemberOutput | None]: return self._execute(context, context.operation, lambda: self._member(x) if (x := self.members.get_by_user_id(user_id)) else None)
    def list_members(self, context, crew_id: int) -> OperationResult[list[CrewMemberOutput]]: return self._execute(context, context.operation, lambda: [self._member(x) for x in self.members.list_by_crew(crew_id)])
    def add_member(self, context, data: CrewMemberInput) -> OperationResult[CrewMemberOutput]:
        def work():
            if self.users.get_by_id(data.user_id) is None: raise self._missing("user", context)
            if self.crews.get_by_id(data.crew_id) is None: raise self._missing("crew", context)
            return self._member(self.members.create(data))
        return self._execute(context, context.operation, work, write=True, actor_required=True)
    def change_crew(self, context, data: CrewMemberInput) -> OperationResult[CrewMemberOutput]: return self._execute(context, context.operation, lambda: self._member(x) if (x := self.members.update_crew(data.user_id, data.crew_id)) else None, write=True, actor_required=True)
    def remove_member(self, context, user_id: int) -> OperationResult[bool]: return self._execute(context, context.operation, lambda: self.members.remove(user_id), write=True, actor_required=True)
