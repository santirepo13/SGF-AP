"""Address lookup, reference validation, reuse, and safe concurrent creation."""

from api.contracts import AddressComponentsInput, AddressCreateInput, AddressOutput, OperationResult
from api.errors import ApplicationError
from api.interfaces.repositories import (
    AddressRepositoryInterface,
    CrossBisCodeRepositoryInterface,
    CrossQuadrantRepositoryInterface,
    CrossSuffixLetterRepositoryInterface,
    NeighborhoodRepositoryInterface,
    RoadBisCodeRepositoryInterface,
    RoadQuadrantRepositoryInterface,
    RoadSuffixLetterRepositoryInterface,
    RoadTypeRepositoryInterface,
)

from api.security import role_operation_authorizer

from ..base import ServiceBase


class AddressService(ServiceBase):
    def __init__(
        self,
        addresses: AddressRepositoryInterface,
        neighborhoods: NeighborhoodRepositoryInterface,
        road_types: RoadTypeRepositoryInterface,
        road_suffix_letters: RoadSuffixLetterRepositoryInterface,
        road_bis_codes: RoadBisCodeRepositoryInterface,
        road_quadrants: RoadQuadrantRepositoryInterface,
        cross_suffix_letters: CrossSuffixLetterRepositoryInterface,
        cross_bis_codes: CrossBisCodeRepositoryInterface,
        cross_quadrants: CrossQuadrantRepositoryInterface,
        **kwargs,
    ):
        if kwargs.get("authorizer") is None:
            kwargs["authorizer"] = role_operation_authorizer
        super().__init__(**kwargs)
        self.addresses = addresses
        self.neighborhoods = neighborhoods
        self._references = (
            (road_types, "road_type_code"),
            (road_suffix_letters, "road_suffix_letter_code"),
            (road_bis_codes, "road_bis_code"),
            (road_quadrants, "road_quadrant_code"),
            (cross_suffix_letters, "cross_suffix_letter_code"),
            (cross_bis_codes, "cross_bis_code"),
            (cross_quadrants, "cross_quadrant_code"),
        )

    @staticmethod
    def _out(value) -> AddressOutput:
        return AddressOutput(**vars(value))

    def get_by_id(self, context, address_id: int) -> OperationResult[AddressOutput]:
        def work():
            value = self.addresses.get_by_id(address_id)
            if value is None:
                raise self._missing("address", context)
            return self._out(value)

        return self._execute(context, "AddressService.get_by_id", work)

    def find_by_components(self, context, components: AddressComponentsInput) -> OperationResult[AddressOutput | None]:
        return self._execute(
            context,
            "AddressService.find_by_components",
            lambda: self._out(value) if (value := self.addresses.find_by_components(components)) else None,
        )

    def create_or_reuse(self, context, data: AddressCreateInput) -> OperationResult[AddressOutput]:
        def work():
            self._validate_references(data, context)
            components = AddressComponentsInput(**vars(data))
            existing = self.addresses.find_by_components(components)
            if existing is not None:
                return self._out(existing)
            created = self.addresses.create_if_absent(data)
            if created is not None:
                return self._out(created)
            canonical = self.addresses.find_by_components(components)
            if canonical is None:
                raise RuntimeError("canonical address was not available after concurrent creation")
            return self._out(canonical)

        return self._execute(
            context,
            "AddressService.create_or_reuse",
            work,
            write=True,
            actor_required=True,
        )

    def format_address(self, context, address_id: int) -> OperationResult[str]:
        def work():
            value = self.addresses.get_by_id(address_id)
            if value is None:
                raise self._missing("address", context)
            road = f"{value.road_type_code} {value.road_number}"
            if value.road_suffix_letter_code:
                road += value.road_suffix_letter_code
            if value.road_bis_code:
                road += f" BIS {value.road_bis_code}"
            cross = f"{value.cross_road_number}"
            if value.cross_suffix_letter_code:
                cross += value.cross_suffix_letter_code
            result = f"{road} # {cross} - {value.door_plate_number}"
            if value.neighborhood_id:
                neighborhood = self.neighborhoods.get_by_id(value.neighborhood_id)
                if neighborhood:
                    result += f", {neighborhood.name}"
            return result

        return self._execute(context, "AddressService.format_address", work)

    def _validate_references(self, data: AddressCreateInput, context) -> None:
        for repository, field in self._references:
            value = getattr(data, field)
            if value is not None and repository.get_by_code(value) is None:
                raise ApplicationError.invalid_reference(
                    field,
                    "La referencia indicada no existe.",
                    entity=field.removesuffix("_code"),
                    correlation_id=context.correlation_id,
                )
        if data.neighborhood_id is not None and self.neighborhoods.get_by_id(data.neighborhood_id) is None:
            raise ApplicationError.invalid_reference(
                "neighborhood_id",
                "La referencia indicada no existe.",
                entity="neighborhood",
                correlation_id=context.correlation_id,
            )
