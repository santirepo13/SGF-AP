"""One compatibility check per interface layer and inventory integrity."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

import inspect

import pytest

from tests.support.component_catalog import REPOSITORY_PAIRS, SERVICE_PAIRS, public_methods
from tests.support.registry import build_cases


def test_every_repository_implementation_matches_its_interface_methods():
    """Compare each repository method's argument names with its interface."""
    assert len(REPOSITORY_PAIRS) == 22
    for interface, implementation in REPOSITORY_PAIRS:
        for name, declaration in interface.__dict__.items():
            if name.startswith("_") or not callable(declaration):
                continue
            expected = list(inspect.signature(declaration).parameters)
            actual = list(inspect.signature(getattr(implementation, name)).parameters)
            assert actual == expected, f"{implementation.__name__}.{name} does not match"


def test_service_implementations_match_their_service_interfaces():
    """Compare service methods, defaults, and return types with their interfaces."""
    assert len(SERVICE_PAIRS) == 7
    for interface, implementation in SERVICE_PAIRS:
        for name, declaration in interface.__dict__.items():
            if name.startswith("_") or not callable(declaration):
                continue
            assert hasattr(implementation, name)
            expected = list(inspect.signature(declaration).parameters)
            implementation_method = getattr(implementation, name)
            expected_signature = inspect.signature(declaration)
            actual_signature = inspect.signature(implementation_method)
            actual = list(actual_signature.parameters)
            assert actual == expected, f"{implementation.__name__}.{name} does not match"
            for parameter_name, expected_parameter in expected_signature.parameters.items():
                actual_parameter = actual_signature.parameters[parameter_name]
                assert actual_parameter.default == expected_parameter.default
            assert inspect.get_annotations(declaration, eval_str=True).get("return") == inspect.get_annotations(implementation_method, eval_str=True).get("return"), f"{implementation.__name__}.{name} return type does not match"


def test_repository_inventory_contains_22_interfaces_and_70_methods():
    """Confirm the repository catalogue contains every promised operation."""
    assert len(REPOSITORY_PAIRS) == 22
    assert sum(len(public_methods(interface)) for interface, _ in REPOSITORY_PAIRS) == 70


def test_service_inventory_contains_7_interfaces_and_55_methods():
    """Confirm the service catalogue contains every promised operation."""
    assert len(SERVICE_PAIRS) == 7
    assert sum(len(public_methods(interface)) for interface, _ in SERVICE_PAIRS) == 55


def test_case_registry_rejects_duplicate_ids_and_preserves_traceability():
    """Keep source-file links for cases and reject duplicate case identifiers."""
    cases = build_cases((
        ("S1-A01", "S1", "active default", "dto", "omitted", "True", __file__),
        ("S8-22", "S8", "single invocation", "double", "valid", "one call", __file__),
    ))
    assert [case.case_id for case in cases] == ["S1-A01", "S8-22"]
    assert all(case.test_file for case in cases)
    with pytest.raises(ValueError):
        build_cases((
            ("DUP", "S1", "r", "p", "i", "e", __file__),
            ("DUP", "S1", "r", "p", "i", "e", __file__),
        ))
