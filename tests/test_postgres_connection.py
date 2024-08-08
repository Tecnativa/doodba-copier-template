import psycopg2
import pytest
from psycopg2 import OperationalError


def test_postgres_connection(traefik_host, data, postgres_service):
    """Test connecting to the PostgreSQL service via the main domain."""
    domain = f"db.{traefik_host['hostname']}"
    port = data["postgres_exposed_port"]

    db_name = "prod"  # Default database name in the PostgreSQL image
    user = "odoo"
    password = "yourpassword"
    connection_string = (
        f"host={domain} port={port} dbname={db_name} user={user} password={password}"
    )

    try:
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result == (1,)
    except OperationalError as e:
        pytest.fail(f"Could not connect to PostgreSQL: {e}")
    finally:
        if conn:
            conn.close()
