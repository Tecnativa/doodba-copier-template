from pathlib import Path

import pytest
from copier import run_copy
from plumbum import local
from python_on_whales import DockerClient

from .conftest import DBVER_PER_ODOO


@pytest.mark.parametrize("backup_deletion", (False, True))
@pytest.mark.parametrize(
    "backup_dst",
    ("", "s3://example", "s3+http://example", "boto3+s3://example", "sftp://example"),
)
@pytest.mark.parametrize("backup_image_version", ("latest"))
@pytest.mark.parametrize("smtp_relay_host", ("", "example"))
def _test_backup_config(
    backup_deletion: bool,
    backup_dst: str,
    backup_image_version: str,
    cloned_template: Path,
    smtp_relay_host: str,
    supported_odoo_version: float,
    tmp_path: Path,
):
    """Test that backup deletion setting is respected."""
    data = {
        "backup_deletion": backup_deletion,
        "backup_dst": backup_dst,
        "backup_image_version": backup_image_version,
        "odoo_version": supported_odoo_version,
        "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
        "smtp_relay_host": smtp_relay_host,
    }
    # Remove parameter if False, to test this is the properly default value
    if not backup_deletion:
        del data["backup_deletion"]
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
        dc_prod = DockerClient(compose_files=["prod.yaml"])
        prod_config = dc_prod.compose.config()
    # Check backup service existence
    if not backup_dst:
        assert "backup" not in prod_config.services
        return
    # Check selected duplicity image
    if "s3" in backup_dst:
        assert prod_config.services[
            "backup"
        ].image == "ghcr.io/tecnativa/docker-duplicity-postgres-s3:{}".format(
            backup_image_version
        )
    else:
        assert (
            prod_config.services["backup"].image
            == f"ghcr.io/tecnativa/docker-duplicity-postgres:{backup_image_version}"
        )
    # Check SMTP configuration
    if smtp_relay_host:
        assert "smtp" in prod_config.services
        assert prod_config.services["backup"].environment["SMTP_HOST"] == "smtplocal"
        assert "EMAIL_FROM" in prod_config.services["backup"].environment
        assert "EMAIL_TO" in prod_config.services["backup"].environment
    else:
        assert "smtp" not in prod_config.services
        assert "SMTP_HOST" not in prod_config.services["backup"].environment
        assert "EMAIL_FROM" not in prod_config.services["backup"].environment
        assert "EMAIL_TO" not in prod_config.services["backup"].environment
    # Check backup deletion
    if backup_deletion:
        assert (
            prod_config.services["backup"].environment["JOB_800_WHAT"]
            == "dup --force remove-older-than 3M $$DST"
        )
        assert prod_config.services["backup"].environment["JOB_800_WHEN"] == "weekly"
    else:
        assert "JOB_800_WHAT" not in prod_config.services["backup"].environment
        assert "JOB_800_WHEN" not in prod_config.services["backup"].environment


def test_dbfilter_default(
    cloned_template: Path, supported_odoo_version: float, tmp_path: Path
):
    """Default DB filter inherits database name and is applied to prod only."""
    with local.cwd(tmp_path):
        run_copy(
            src_path=str(cloned_template),
            dst_path=".",
            data={
                "odoo_version": supported_odoo_version,
                "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
                "backup_dst": "file:///here",
            },
            vcs_ref="test",
            defaults=True,
            overwrite=True,
            unsafe=True,
        )
        devel, test, prod = map(
            lambda env: DockerClient(compose_files=[f"{env}.yaml"]).compose.config(),
            ("devel", "test", "prod"),
        )
        assert "DB_FILTER" not in devel.services["odoo"].environment
        assert "DB_FILTER" not in test.services["odoo"].environment
        assert prod.services["odoo"].environment["DB_FILTER"] == "^prod"
        assert prod.services["backup"].environment["DBS_TO_INCLUDE"] == "^prod"


def test_dbfilter_custom_odoo_extensions(
    cloned_template: Path, supported_odoo_version: float, tmp_path: Path
):
    """Fixes custom Odoo regexp extensions in dbfilter for the backup service."""
    with local.cwd(tmp_path):
        run_copy(
            src_path=str(cloned_template),
            dst_path=".",
            data={
                "odoo_version": supported_odoo_version,
                "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
                "backup_dst": "file:///here",
                "odoo_dbfilter": "^%d_%h$",
            },
            vcs_ref="test",
            defaults=True,
            overwrite=True,
            unsafe=True,
        )
        prod = DockerClient(compose_files=["prod.yaml"]).compose.config()
        assert prod.services["odoo"].environment["DB_FILTER"] == "^%d_%h$$"
        assert prod.services["backup"].environment["DBS_TO_INCLUDE"] == "^.*_.*$$"
