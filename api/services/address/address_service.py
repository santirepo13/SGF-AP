"""Address lookup, validation, reuse and formatting service."""
from api.contracts import AddressComponentsInput, AddressCreateInput, AddressOutput
from api.interfaces.repositories import AddressRepositoryInterface, NeighborhoodRepositoryInterface, RoadTypeRepositoryInterface, RoadSuffixLetterRepositoryInterface, RoadBisCodeRepositoryInterface, RoadQuadrantRepositoryInterface, CrossSuffixLetterRepositoryInterface, CrossBisCodeRepositoryInterface, CrossQuadrantRepositoryInterface
from ..base import ServiceBase

class AddressService(ServiceBase):
    def __init__(self, addresses: AddressRepositoryInterface, neighborhoods: NeighborhoodRepositoryInterface, road_types: RoadTypeRepositoryInterface, road_suffix_letters: RoadSuffixLetterRepositoryInterface, road_bis_codes: RoadBisCodeRepositoryInterface, road_quadrants: RoadQuadrantRepositoryInterface, cross_suffix_letters: CrossSuffixLetterRepositoryInterface, cross_bis_codes: CrossBisCodeRepositoryInterface, cross_quadrants: CrossQuadrantRepositoryInterface, **kwargs):
        super().__init__(**kwargs); self.addresses = addresses; self.neighborhoods = neighborhoods; self.refs = ((road_types, "road_type_code"), (road_suffix_letters, "road_suffix_letter_code"), (road_bis_codes, "road_bis_code"), (road_quadrants, "road_quadrant_code"), (cross_suffix_letters, "cross_suffix_letter_code"), (cross_bis_codes, "cross_bis_code"), (cross_quadrants, "cross_quadrant_code"))
    def _out(self, value): return AddressOutput(**vars(value))
    def obtener_por_id(self, context, address_id: int):
        def work():
            value = self.addresses.get_by_id(address_id)
            return self._out(value) if value else None
        return self._execute(context, context.operation, work)
    def buscar_por_componentes(self, context, components: AddressComponentsInput):
        return self._execute(context, context.operation, lambda: self._out(value) if (value := self.addresses.find_by_components(components)) else None)
    def crear_o_reutilizar(self, context, data: AddressCreateInput):
        def work():
            existing = self.addresses.find_by_components(AddressComponentsInput(**vars(data)))
            return self._out(existing or self.addresses.create(data))
        return self._execute(context, context.operation, work, write=True)
    def obtener_representacion(self, context, address_id: int):
        def work():
            value = self.addresses.get_by_id(address_id)
            if value is None: raise self._missing("address", context)
            road = f"{value.road_type_code} {value.road_number}"
            if value.road_suffix_letter_code: road += value.road_suffix_letter_code
            if value.road_bis_code: road += f" BIS {value.road_bis_code}"
            cross = f"{value.cross_road_number}"
            if value.cross_suffix_letter_code: cross += value.cross_suffix_letter_code
            return f"{road} # {cross} - {value.door_plate_number}"
        return self._execute(context, context.operation, work)
