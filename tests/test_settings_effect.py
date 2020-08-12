from pathlib import Path
from typing import Union

import pytest
import yaml
from copier.main import copy
from plumbum import local
from plumbum.cmd import docker_compose


@pytest.mark.parametrize("backup_deletion", (False, True))
@pytest.mark.parametrize(
    "backup_dst",
    (None, "s3://example", "s3+http://example", "boto3+s3://example", "sftp://example"),
)
@pytest.mark.parametrize("smtp_relay_host", (None, "example"))
def test_backup_config(
    backup_deletion: bool,
    backup_dst: Union[None, str],
    cloned_template: Path,
    smtp_relay_host: Union[None, str],
    supported_odoo_version: float,
    tmp_path: Path,
):
    """Test that backup deletion setting is respected."""
    data = {
        "backup_deletion": backup_deletion,
        "backup_dst": backup_dst,
        "odoo_version": supported_odoo_version,
        "smtp_relay_host": smtp_relay_host,
    }
    # Remove parameter if False, to test this is the properly default value
    if not backup_deletion:
        del data["backup_deletion"]
    with local.cwd(tmp_path):
        copy(
            src_path=str(cloned_template),
            dst_path=".",
            vcs_ref="test",
            force=True,
            data=data,
        )
        prod = yaml.safe_load(docker_compose("-f", "prod.yaml", "config"))
    # Check backup service existence
    if not backup_dst:
        assert "backup" not in prod["services"]
        return
    # Check selected duplicity image
    if "s3" in backup_dst:
        assert prod["services"]["backup"]["image"] == "tecnativa/duplicity:postgres-s3"
    else:
        assert prod["services"]["backup"]["image"] == "tecnativa/duplicity:postgres"
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
