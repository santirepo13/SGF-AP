"""Central errors, SQL failure classification and public-data protection."""

if __name__ == "__main__":
    # Direct execution hands this file to pytest so its fixtures and assertions run.
    import sys
    from pathlib import Path
    import pytest

    project_root = next(parent for parent in Path(__file__).resolve().parents if (parent / "pytest.ini").is_file())
    sys.path.insert(0, str(project_root))
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))

import pytest

from api.contracts import ErrorDetail, ExecutionContext
from api.errors import ApplicationError, ErrorCatalog, ErrorCode, ErrorHandler, PersistenceContext


class TechnicalError(Exception):
    """Stand in for a database exception carrying a technical failure code."""
    def __init__(self, sqlstate=None, *, column_name=None, table_name=None):
        """Expose the diagnostic fields read by persistence error handling."""
        super().__init__("technical details must stay internal")
        self.sqlstate = sqlstate
        self.diag = type(
            "Diagnostic",
            (),
            {"sqlstate": sqlstate, "column_name": column_name, "table_name": table_name},
        )()


def test_error_code_catalog_is_complete_and_immutable():
    """Every public error has one catalogue definition that cannot be changed."""
    assert set(ErrorCatalog.definitions) == set(ErrorCode)
    assert len(ErrorCatalog.all()) == 11
    with pytest.raises(TypeError):
        ErrorCatalog.definitions[ErrorCode.INVALID_VALUE] = ErrorCatalog.get(ErrorCode.INVALID_VALUE)


def test_application_error_uses_catalog_and_preserves_cause():
    """Use the catalogue message while retaining the private cause internally."""
    cause = RuntimeError("private database detail")
    error = ApplicationError.invalid_reference("role_id", "La referencia no existe.", cause=cause)
    assert error.code is ErrorCode.INVALID_REFERENCE
    assert error.message == ErrorCatalog.get(ErrorCode.INVALID_REFERENCE).message
    assert error.cause is cause
    assert error.__cause__ is cause


def test_public_error_reuses_scrum_one_contract_without_cause():
    """Expose safe error details and correlation without exposing the cause."""
    cause = RuntimeError("private detail")
    error = ApplicationError.invalid_value("road_number", "Debe estar entre 1 y 999.", cause=cause)
    result = ErrorHandler.to_public(error, ExecutionContext("create_address", "corr-1"))
    assert result.code == "VAL-002"
    assert result.message == "Uno o más datos tienen un tipo, formato o valor inválido."
    assert result.correlation_id == "corr-1"
    assert result.details == (ErrorDetail("road_number", None, "Debe estar entre 1 y 999."),)
    assert not hasattr(result, "cause")
    assert "private" not in result.message


def test_existing_correlation_is_preserved_and_missing_one_is_generated():
    """Keep an existing request reference or create one when missing."""
    known = ApplicationError.unexpected(correlation_id="existing")
    assert ErrorHandler.to_public(known).correlation_id == "existing"
    generated = ErrorHandler.to_public(ApplicationError.unexpected())
    assert generated.correlation_id


@pytest.mark.parametrize(
    ("sqlstate", "expected", "input_origin"),
    [
        ("23502", ErrorCode.REQUIRED_FIELD_MISSING, True),
        ("23503", ErrorCode.INVALID_REFERENCE, True),
        ("23505", ErrorCode.UNIQUE_CONFLICT, True),
        ("23514", ErrorCode.INVALID_VALUE, True),
        ("22001", ErrorCode.INVALID_VALUE, True),
        ("22P02", ErrorCode.INVALID_VALUE, True),
        ("22003", ErrorCode.INVALID_VALUE, True),
        ("08006", ErrorCode.PERSISTENCE_FAILURE, False),
        ("40001", ErrorCode.PERSISTENCE_FAILURE, False),
        ("40P01", ErrorCode.PERSISTENCE_FAILURE, False),
    ],
)
def test_persistence_sqlstate_translation(sqlstate, expected, input_origin):
    """Classify each database failure according to its cause and input origin."""
    technical = TechnicalError(sqlstate, column_name="road_number", table_name="addresses")
    error = ErrorHandler.translate_persistence(
        technical,
        ExecutionContext("create_address", "corr-sql"),
        persistence_context=PersistenceContext("create_address", "addresses", "road_number", input_origin),
    )
    assert error.code is expected
    assert error.cause is technical if expected is ErrorCode.PERSISTENCE_FAILURE else True


def test_not_null_from_internal_write_is_not_user_validation():
    """Do not blame user input for a missing value in an internal database write."""
    error = ErrorHandler.translate_persistence(
        TechnicalError("23502", column_name="status_id", table_name="tickets"),
        persistence_context=PersistenceContext("save_ticket", "tickets", "status_id", False),
    )
    assert error.code is ErrorCode.PERSISTENCE_FAILURE


def test_unexpected_exception_is_sys_002_and_technical_message_is_hidden():
    """Return a safe internal error without leaking a secret from the exception."""
    cause = RuntimeError("password=secret")
    output = ErrorHandler.handle(cause, ExecutionContext("save_ticket", "corr-unexpected"))
    assert output.code == "SYS-002"
    assert output.message == "Ocurrió un error interno inesperado."
    assert "secret" not in output.message


def test_known_error_keeps_its_code_through_handler():
    """Keep a known permission failure and its original request reference."""
    error = ApplicationError.forbidden("assign_ticket", correlation_id="corr-known")
    output = ErrorHandler.handle(error, ExecutionContext("assign_ticket", "other"))
    assert output.code == "PER-001"
    assert output.correlation_id == "corr-known"


@pytest.mark.parametrize("code", tuple(ErrorCode), ids=lambda code: f"S3-{code.name}")
def test_every_error_code_has_one_catalog_message(code):
    """Check each catalogue entry has its own code, message, and category."""
    definition = ErrorCatalog.get(code)
    assert definition.code is code
    assert definition.message
    assert definition.category
