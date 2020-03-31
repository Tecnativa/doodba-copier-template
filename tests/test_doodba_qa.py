import os

import pytest
from copier.main import copy
from plumbum import FG

from .helpers import CURRENT_ODOO_VERSIONS

try:
    from plumbum.cmd import docker
except ImportError:
    docker = None


@pytest.mark.skipif(docker is None, reason="Need docker CLI to test doodba-qa")
@pytest.mark.skipif(
    os.environ.get("QA_TEST") != "1", reason="Missing QA_TEST=1 env variable"
)
@pytest.mark.parametrize("odoo_version", CURRENT_ODOO_VERSIONS)
def test_doodba_qa(tmpdir, odoo_version):
    """Test Doodba QA works fine with a scaffolding copy."""
    copy(
        ".", tmpdir, data={"odoo_version": odoo_version}, force=True, vcs_ref="HEAD",
    )
    qa_run = docker[
        "container",
        "run",
        "--rm",
        "--privileged",
        f"-v{tmpdir}:{tmpdir}:z",
        "-v/var/run/docker.sock:/var/run/docker.sock:z",
        f"-w{tmpdir}",
        "-eADDON_CATEGORIES=-p",
        "-eCOMPOSE_FILE=test.yaml",
        f"-eODOO_MAJOR={int(odoo_version)}",
        f"-eODOO_MINOR={odoo_version:.1f}",
        "tecnativa/doodba-qa",
    ]
    try:
        qa_run["secrets-setup"] & FG
        qa_run["networks-autocreate"] & FG
        qa_run["build"] & FG
        qa_run["closed-prs"] & FG
        qa_run["flake8"] & FG
        qa_run["pylint"] & FG
        qa_run["addons-install"] & FG
        qa_run["coverage"] & FG
    finally:
        qa_run["shutdown"] & FG
        docker["system", "prune", "--all", "--force", "--volumes"]
