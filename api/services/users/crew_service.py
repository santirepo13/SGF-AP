from api.contracts import CrewCreateInput, CrewMemberInput, CrewMemberOutput, CrewOutput, CrewUpdateInput
from api.interfaces.repositories import CrewMemberRepositoryInterface, CrewRepositoryInterface, UserRepositoryInterface
from ..base import ServiceBase

class CrewService(ServiceBase):
    def __init__(self, crews: CrewRepositoryInterface, members: CrewMemberRepositoryInterface, users: UserRepositoryInterface, **kwargs): super().__init__(**kwargs); self.crews, self.members, self.users = crews, members, users
    @staticmethod
    def _crew(x): return CrewOutput(x.id, x.name)
    @staticmethod
    def _member(x): return CrewMemberOutput(x.user_id, x.crew_id)
    def obtener_por_id(self, context, crew_id: int): return self._execute(context, context.operation, lambda: self._crew(x) if (x := self.crews.get_by_id(crew_id)) else None)
    def listar(self, context): return self._execute(context, context.operation, lambda: [self._crew(x) for x in self.crews.list_all()])
    def crear(self, context, data: CrewCreateInput): return self._execute(context, context.operation, lambda: self._crew(self.crews.create(data)), write=True, actor_required=True)
    def actualizar(self, context, data: CrewUpdateInput): return self._execute(context, context.operation, lambda: self._crew(x) if (x := self.crews.update(data)) else None, write=True, actor_required=True)
    def consultar_pertenencia(self, context, user_id: int): return self._execute(context, context.operation, lambda: self._member(x) if (x := self.members.get_by_user_id(user_id)) else None)
    def listar_integrantes(self, context, crew_id: int): return self._execute(context, context.operation, lambda: [self._member(x) for x in self.members.list_by_crew(crew_id)])
    def incorporar_integrante(self, context, data: CrewMemberInput):
        def work():
            if self.users.get_by_id(data.user_id) is None: raise self._missing("user", context)
            if self.crews.get_by_id(data.crew_id) is None: raise self._missing("crew", context)
            return self._member(self.members.create(data))
        return self._execute(context, context.operation, work, write=True, actor_required=True)
    def cambiar_cuadrilla(self, context, data: CrewMemberInput): return self._execute(context, context.operation, lambda: self._member(x) if (x := self.members.update_crew(data.user_id, data.crew_id)) else None, write=True, actor_required=True)
    def retirar_integrante(self, context, user_id: int): return self._execute(context, context.operation, lambda: self.members.remove(user_id), write=True, actor_required=True)
