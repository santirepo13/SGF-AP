import os

import pytest

from api.config import PostgresConnectionProvider, load_database_config


@pytest.mark.integration
def test_postgresql_read_and_connection_close():
    if os.getenv("RUN_POSTGRES_INTEGRATION") != "1":
        pytest.skip("PostgreSQL integration tests are opt-in")
    config = load_database_config()
    with PostgresConnectionProvider(config).connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
