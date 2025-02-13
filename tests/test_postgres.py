import uuid
from pathlib import Path

import pytest
from copier import run_copy
from plumbum import local
from python_on_whales import DockerClient

from .conftest import DBVER_PER_ODOO

try:
    from python_on_whales.components.compose.models import ComposeConfig
except ImportError:
    ComposeConfig = None


def _get_db_service_name(dc: DockerClient) -> str:
    config_data = dc.compose.config()

    # (1) In newer versions of python-on-whales:
    #     config_data is a ComposeConfig => config_data.services is a dict:
    #       { "service_name": ServiceConfig(...) }
    # (2) In older versions: config_data is a "legacy" dict
    #       => config_data["services"] => { "service_name": {...} }

    if ComposeConfig and isinstance(config_data, ComposeConfig):
        services_dict = config_data.services
    else:
        services_dict = config_data["services"]
    for svc_name in services_dict:
        if svc_name.lower().endswith("-db"):
            return svc_name
    for svc_name in services_dict:
        if "postgres" in svc_name.lower() or "db" in svc_name.lower():
            return svc_name
    return "db"


@pytest.mark.parametrize("dbver", ("oldest", "latest"))
def test_postgresql_client_versions(
    cloned_template: Path,
    supported_odoo_version: float,
    tmp_path: Path,
    dbver: str,
):
    """Test multiple postgresql-client versions in odoo, db and duplicity services"""
    unique_project_name = f"test_{uuid.uuid4().hex}"
    dc_prod = DockerClient(
        compose_files=["prod.yaml"],
        compose_project_name=unique_project_name,
    )

    dbver_raw = DBVER_PER_ODOO[supported_odoo_version][dbver]
    dbver_mver = dbver_raw.split(".")[0]

    with local.cwd(tmp_path):
        print(str(cloned_template))

        run_copy(
            str(cloned_template),
            dst_path=".",
            data={
                "odoo_version": supported_odoo_version,
                "project_name": unique_project_name,
                "odoo_proxy": "",
                "postgres_version": dbver_raw,
                "backup_dst": "/tmp/dummy",
            },
            vcs_ref="test",
            defaults=True,
            overwrite=True,
            unsafe=True,
        )
        try:
            dc_prod.compose.build()
            db_svc = _get_db_service_name(dc_prod)
            odoo_pgdump_stdout = dc_prod.compose.run(
                "odoo",
                command=["pg_dump", "--version"],
                remove=True,
                tty=False,
            )
            odoo_pgdump_mver = (
                odoo_pgdump_stdout.splitlines()[-1].strip().split(" ")[2].split(".")[0]
            )
            db_pgdump_stdout = dc_prod.compose.run(
                db_svc,
                command=["pg_dump", "--version"],
                remove=True,
                tty=False,
            )
            db_pgdump_mver = (
                db_pgdump_stdout.splitlines()[-1].strip().split(" ")[2].split(".")[0]
            )
            backup_pgdump_stdout = dc_prod.compose.run(
                "backup",
                command=["pg_dump", "--version"],
                remove=True,
                tty=False,
            )
            backup_pgdump_mver = (
                backup_pgdump_stdout.splitlines()[-1]
                .strip()
                .split(" ")[2]
                .split(".")[0]
            )
            assert (
                odoo_pgdump_mver == db_pgdump_mver == backup_pgdump_mver == dbver_mver
            )
        finally:
            dc_prod.compose.rm(stop=True, volumes=True)
