from pathlib import Path

from copier import run_copy
from python_on_whales import DockerClient

from .conftest import DBVER_PER_ODOO


def test_doodba_qa(tmp_path: Path, supported_odoo_version: float):
    """Test Doodba QA works fine with a scaffolding copy."""
    run_copy(
        ".",
        tmp_path,
        data={
            "odoo_version": supported_odoo_version,
            "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
        },
        vcs_ref="HEAD",
        defaults=True,
        overwrite=True,
        unsafe=True,
    )
    docker = DockerClient()

    def _execute_qa(cmd):
        return docker.run(
            "tecnativa/doodba-qa",
            command=cmd,
            envs={
                "ADDON_CATEGORIES": "-p",
                "COMPOSE_FILE": "test.yaml",
                "ODOO_VERSION": supported_odoo_version,
            },
            privileged=True,
            remove=True,
            volumes=[
                (tmp_path, tmp_path, "z"),
                ("/var/run/docker.sock", "/var/run/docker.sock", "z"),
            ],
            workdir=tmp_path,
        )

    try:
        _execute_qa(["secrets-setup"])
        _execute_qa(["networks-autocreate"])
        _execute_qa(["build"])
        _execute_qa(["closed-prs"])
        _execute_qa(["flake8"])
        _execute_qa(["pylint"])
        _execute_qa(["addons-install"])
        _execute_qa(["coverage"])
    finally:
        _execute_qa(["shutdown"])
