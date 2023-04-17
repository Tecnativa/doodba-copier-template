import uuid
from pathlib import Path

import pytest
from copier.main import run_auto
from plumbum import local

from .conftest import DBVER_PER_ODOO, docker_compose


@pytest.mark.parametrize("dbver", ("oldest", "latest"))
def test_postgresql_client_versions(
    cloned_template: Path,
    supported_odoo_version: float,
    tmp_path: Path,
    dbver: str,
):
    """Test multiple postgresql-client versions in odoo, db and duplicity services"""
    dbver_raw = DBVER_PER_ODOO[supported_odoo_version][dbver]
    dbver_mver = dbver_raw.split(".")[0]
    dc = docker_compose("-f", "prod.yaml")
    with local.cwd(tmp_path):
        print(str(cloned_template))
        assert True
        run_auto(
            str(cloned_template),
            dst_path=".",
            data={
                "odoo_version": supported_odoo_version,
                "project_name": uuid.uuid4().hex,
                "odoo_proxy": "",
                "postgres_version": dbver_raw,
                "backup_dst": "/tmp/dummy",
            },
            vcs_ref="test",
            defaults=True,
            overwrite=True,
        )
        try:
            dc("build")
            odoo_pgdump_stdout = docker_compose(
                "-f",
                "prod.yaml",
                "run",
                "--rm",
                "--entrypoint",
                "pg_dump",
                "odoo",
                "--version",
            )
            odoo_pgdump_mver = (
                odoo_pgdump_stdout.splitlines()[-1].strip().split(" ")[2].split(".")[0]
            )
            db_pgdump_stdout = docker_compose(
                "-f",
                "prod.yaml",
                "run",
                "--rm",
                "--entrypoint",
                "pg_dump",
                "db",
                "--version",
            )
            db_pgdump_mver = (
                db_pgdump_stdout.splitlines()[-1].strip().split(" ")[2].split(".")[0]
            )
            backup_pgdump_stdout = docker_compose(
                "-f",
                "prod.yaml",
                "run",
                "--rm",
                "backup",
                "pg_dump",
                "--version",
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
            dc("down", "--volumes", "--remove-orphans")
