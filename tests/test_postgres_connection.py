import time
import uuid
from pathlib import Path

import psycopg2
import pytest
from copier import run_copy
from packaging import version
from plumbum import local
from python_on_whales import DockerClient

from .conftest import DBVER_PER_ODOO


@pytest.mark.parametrize("environment", ("prod",))
def test_database_external_connection(
    cloned_template: Path,
    supported_odoo_version: float,
    tmp_path: Path,
    traefik_host: dict,
    environment: str,
):
    """Test that database is accessible via Traefik."""
    traefik_version = version.parse(traefik_host["traefik_version"])
    if traefik_version < version.parse("3"):
        pytest.skip("This test only runs with Traefik v3 or higher")

    base_domain = traefik_host["hostname"]
    data = {
        "odoo_listdb": True,
        "traefik_version": int(
            str(version.parse(traefik_host["traefik_version"])).split(".")[0]
        ),
        "postgres_exposed": True,
        "odoo_version": supported_odoo_version,
        "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
        "paths_without_crawlers": ["/web/login", "/web/database"],
        "project_name": uuid.uuid4().hex,
        f"domains_{environment}": [
            {"hosts": [f"db.{base_domain}"], "cert_resolver": False}
        ],
        "db_environment_extra": {
            "WAN_DATABASES": '["prod"]',
            "WAN_USERS": '["odoo"]',
        },
    }
    if supported_odoo_version < 16:
        data["postgres_version"] = 13

    dc = DockerClient(compose_files=[f"{environment}.yaml"])
    with local.cwd(tmp_path):
        run_copy(
            src_path=str(cloned_template),
            dst_path=".",
            data=data,
            vcs_ref="test",
            defaults=True,
            overwrite=True,
            unsafe=True,
        )
        try:
            dc.compose.build()
            dc.compose.up(detach=True)
            # Wait for the services to be ready
            max_retries = 30
            delay = 2
            connected = False
            for _ in range(max_retries):
                try:
                    connection = psycopg2.connect(
                        dbname="postgres",
                        user="odoo",
                        password="odoo",
                        host=traefik_host["hostname"],
                        port=5432,
                        connect_timeout=1,
                        sslmode="disable",
                    )
                    cursor = connection.cursor()
                    cursor.execute("SELECT 1;")
                    result = cursor.fetchone()
                    assert result == (1,)
                    connected = True
                    break
                except Exception as e:
                    last_exception = e  # Almacena la excepción
                    time.sleep(delay)
            assert connected, f"Could not connect to databse: {last_exception}"
        finally:
            dc.compose.down(remove_images="local", remove_orphans=True)
