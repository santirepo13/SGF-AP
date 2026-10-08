from api.contracts import AddressComponentsInput, AddressCreateInput
from ..mapping import address
from ..persistence import RepositoryBase

_COLUMNS = "id, road_type_code, road_number, road_suffix_letter_code, road_bis_code, road_bis_suffix, road_quadrant_code, cross_road_number, cross_suffix_letter_code, cross_bis_code, cross_bis_suffix, cross_quadrant_code, door_plate_number, neighborhood_id, created_at"
_COMPONENTS = "road_type_code, road_number, road_suffix_letter_code, road_bis_code, road_bis_suffix, road_quadrant_code, cross_road_number, cross_suffix_letter_code, cross_bis_code, cross_bis_suffix, cross_quadrant_code, door_plate_number, neighborhood_id"

class AddressRepository(RepositoryBase):
    def get_by_id(self, address_id: int):
        return self.fetch_one(f"SELECT {_COLUMNS} FROM addresses WHERE id = %s", (address_id,), operation="addresses.get_by_id", entity="address", mapper=address)
    def find_by_components(self, components: AddressComponentsInput):
        parts = [getattr(components, name) for name in _COMPONENTS.split(", ")]
        where = " AND ".join(f"{name} IS NOT DISTINCT FROM %s" for name in _COMPONENTS.split(", "))
        return self.fetch_one(f"SELECT {_COLUMNS} FROM addresses WHERE {where}", tuple(parts), operation="addresses.find_by_components", entity="address", mapper=address)
    def list_by_neighborhood(self, neighborhood_id: int):
        return self.fetch_all(f"SELECT {_COLUMNS} FROM addresses WHERE neighborhood_id = %s ORDER BY id", (neighborhood_id,), operation="addresses.list_by_neighborhood", entity="address", mapper=address)
    def create(self, data: AddressCreateInput):
        names = _COMPONENTS.split(", ")
        values = tuple(getattr(data, name) for name in names)
        placeholders = ", ".join(["%s"] * len(names))
        return self.execute_one(f"INSERT INTO addresses ({_COMPONENTS}) VALUES ({placeholders}) RETURNING {_COLUMNS}", values, operation="addresses.create", entity="address", mapper=address)
