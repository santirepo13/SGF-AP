"""Regression checks for case-specific CSV explanations."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

from pathlib import Path

import pytest

from tests.coverage import _explanation, write_csv


def test_parameterized_explanations_identify_each_scenario():
    """Explain every configuration and database failure in distinct plain words."""
    # Build the same parameter variants that appear as separate CSV rows.
    cases = [
        (
            "test_missing_database_parameter_is_invalid",
            {"missing": repr(setting)},
            setting,
        )
        for setting in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    ]
    cases.extend(
        ("test_invalid_port_is_rejected", {"port": repr(port)}, port)
        for port in ("not-a-number", "0", "65536")
    )
    cases.extend(
        (
            "test_persistence_sqlstate_translation",
            {
                "sqlstate": repr(sqlstate),
                "expected": f"<ErrorCode.INVALID_VALUE: '{expected}'>",
                "input_origin": str(input_origin),
            },
            sqlstate,
        )
        for sqlstate, expected, input_origin in (
            ("23502", "VAL-001", True),
            ("23503", "REL-001", True),
            ("23505", "CON-001", True),
            ("23514", "VAL-002", True),
            ("22001", "VAL-002", True),
            ("22P02", "VAL-002", True),
            ("22003", "VAL-002", True),
            ("08006", "SYS-001", False),
            ("40001", "SYS-001", False),
            ("40P01", "SYS-001", False),
        )
    )

    # Generate one explanation per variant, then reject codes and duplicates.
    explanations = [
        _explanation(
            {"parameters": parameters},
            f"tests/example.py::{name}[{scenario}]",
            f"AUTO.example.py.{name}",
        )
        for name, parameters, scenario in cases
    ]

    assert len(explanations) == len(set(explanations))
    assert all(explanation.startswith("When ") for explanation in explanations)
    assert all(scenario not in explanation for (_, _, scenario), explanation in zip(cases, explanations))
    assert "required input is missing" in explanations[8]
    assert "invalid reference" in explanations[9]
    assert "database connection fails" in explanations[-3]
    assert all("SQLSTATE" not in explanation and "VAL-" not in explanation and "SYS-" not in explanation
               for explanation in explanations)


def test_component_explanations_describe_operations_without_case_or_method_codes():
    """Name the affected repository or service operation without machine codes."""
    repository_trace = {
        "parameters": {
            "implementation": "<class 'api.repositories.geolocation.municipality_repository.MunicipalityRepository'>",
            "method": "'get_by_id'",
        },
    }
    service_trace = {
        "parameters": {
            "implementation": "<class 'api.services.geolocation.catalog_service.CatalogService'>",
            "method": "'list_municipalities'",
        },
    }

    missing = _explanation(repository_trace, "tests/repositories/test_repositories.py::test_absence", "R4-01.N")
    failed = _explanation(repository_trace, "tests/repositories/test_repositories.py::test_failure", "R4-01.E")
    service = _explanation(service_trace, "tests/services/test_services.py::test_failure", "S6-01.E")

    assert "municipality record" in missing and "returns no record" in missing
    assert "municipality record" in failed and "original cause" in failed
    assert "municipalities" in service and "tracking reference" in service
    assert all("R4-" not in explanation and "S6-" not in explanation and "get_by_id" not in explanation
               for explanation in (missing, failed, service))


def test_catalog_and_enum_explanations_use_readable_names():
    """Use natural language for catalogue errors and stored enum values."""
    catalog = _explanation({}, "tests/errors/test_errors.py::test_every_error_code[S3-INACTIVE_USER]", "S3-INACTIVE_USER")
    direct = _explanation(
        {},
        "tests/config/test_database.py::test_load_database_config_from_dotenv_file",
        "AUTO.test_database.py.test_load_database_config_from_dotenv_file",
    )
    enum = _explanation(
        {"parameters": {"enum_type": "<enum 'StatusName'>", "value": "'InProgress'"}},
        "tests/models/test_models.py::test_enum_sql_round_trip_is_individual[StatusName.InProgress]",
        "AUTO.test_models.py.test_enum_sql_round_trip_is_individual",
    )

    assert "user account is inactive" in catalog
    assert "S3-" not in catalog
    assert direct.startswith("Database settings are loaded from the local configuration file")
    assert "ticket status value 'in progress'" in enum
    assert "<enum" not in enum


def test_csv_rejects_duplicate_explanations(tmp_path: Path):
    """Refuse CSV output when two case explanations differ only in casing or spaces."""
    csv_path = tmp_path / "results.csv"
    rows = [
        {"id": "CASE-1", "explanation": "Same explanation"},
        {"id": "CASE-2", "explanation": "  SAME   explanation  "},
    ]

    with pytest.raises(ValueError, match="Duplicate explanation for case CASE-2"):
        write_csv(rows, csv_path)

    assert not csv_path.exists()
