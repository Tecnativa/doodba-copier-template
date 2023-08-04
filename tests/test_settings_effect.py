from pathlib import Path
from typing import Union

import pytest
import yaml
from copier.main import run_auto
from plumbum import local
from plumbum.cmd import docker_compose

from .conftest import DBVER_PER_ODOO


@pytest.mark.parametrize("backup_deletion", (False, True))
@pytest.mark.parametrize(
    "backup_dst",
    (None, "s3://example", "s3+http://example", "boto3+s3://example", "sftp://example"),
)
@pytest.mark.parametrize("backup_image_version", ("latest"))
@pytest.mark.parametrize("smtp_relay_host", (None, "example"))
def test_backup_config(
    backup_deletion: bool,
    backup_dst: Union[None, str],
    backup_image_version: str,
    cloned_template: Path,
    smtp_relay_host: Union[None, str],
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
        run_auto(
            src_path=str(cloned_template),
            dst_path=".",
            data=data,
            vcs_ref="test",
            defaults=True,
            overwrite=True,
        )
        prod = yaml.safe_load(docker_compose("-f", "prod.yaml", "config"))
    # Check backup service existence
    if not backup_dst:
        assert "backup" not in prod["services"]
        return
    # Check selected duplicity image
    if "s3" in backup_dst:
        assert prod["services"]["backup"][
            "image"
        ] == "ghcr.io/tecnativa/docker-duplicity-postgres-s3:{}".format(
            backup_image_version
        )
    else:
        assert prod["services"]["backup"][
            "image"
        ] == "ghcr.io/tecnativa/docker-duplicity-postgres:{}".format(
            backup_image_version
        )
    # Check SMTP configuration
    if smtp_relay_host:
        assert "smtp" in prod["services"]
        assert prod["services"]["backup"]["environment"]["SMTP_HOST"] == "smtplocal"
        assert "EMAIL_FROM" in prod["services"]["backup"]["environment"]
        assert "EMAIL_TO" in prod["services"]["backup"]["environment"]
    else:
        assert "smtp" not in prod["services"]
        assert "SMTP_HOST" not in prod["services"]["backup"]["environment"]
        assert "EMAIL_FROM" not in prod["services"]["backup"]["environment"]
        assert "EMAIL_TO" not in prod["services"]["backup"]["environment"]
    # Check backup deletion
    if backup_deletion:
        assert (
            prod["services"]["backup"]["environment"]["JOB_800_WHAT"]
            == "dup --force remove-older-than 3M $$DST"
        )
        assert prod["services"]["backup"]["environment"]["JOB_800_WHEN"] == "weekly"
    else:
        assert "JOB_800_WHAT" not in prod["services"]["backup"]["environment"]
        assert "JOB_800_WHEN" not in prod["services"]["backup"]["environment"]


def test_dbfilter_default(
    cloned_template: Path, supported_odoo_version: float, tmp_path: Path
):
    """Default DB filter inherits database name and is applied to prod only."""
    with local.cwd(tmp_path):
        run_auto(
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
        )
        devel, test, prod = map(
            lambda env: yaml.safe_load(docker_compose("-f", f"{env}.yaml", "config")),
            ("devel", "test", "prod"),
        )
        assert "DB_FILTER" not in devel["services"]["odoo"]["environment"]
        assert "DB_FILTER" not in test["services"]["odoo"]["environment"]
        assert prod["services"]["odoo"]["environment"]["DB_FILTER"] == "^prod"
        assert prod["services"]["backup"]["environment"]["DBS_TO_INCLUDE"] == "^prod"
