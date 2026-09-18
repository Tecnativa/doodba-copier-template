from pathlib import Path

from copier import run_copy
from plumbum.cmd import invoke
from python_on_whales import docker
from python_on_whales.exceptions import DockerException

from .conftest import override_odoo_entrypoint, safe_stop_env


def test_selective_proxy(
    cloned_template: Path,
    supported_odoo_version: float,
    cloned_project_path: Path,
):
    """Test that the selective access proxy actually works"""
    run_copy(
        str(cloned_template),
        str(cloned_project_path),
        data={
            "odoo_version": supported_odoo_version,
            "postgres_dbname": "devel",
            "whitelisted_hosts_devel": ["www.google.com"],
        },
        vcs_ref="HEAD",
        defaults=True,
        overwrite=True,
        unsafe=True,
    )
    safe_stop_env(cloned_project_path)
    invoke("img-build")
    override_odoo_entrypoint(cloned_project_path)
    docker.compose.up(detach=True)
    # If no error is thrown, http get went right
    docker.compose.execute(
        service="odoo", command=["curl", "-m 1", "www.google.com"], tty=False
    )
    noproxy_failed = False
    try:
        docker.compose.execute(
            service="odoo",
            command=["curl", "-m 1", "www.googleapis.com"],
            tty=False,
        )
    except DockerException:
        noproxy_failed = True
    assert noproxy_failed
