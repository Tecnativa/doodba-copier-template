from pathlib import Path

import pytest
from copier import run_copy
from plumbum.cmd import invoke
from python_on_whales import docker
from python_on_whales.exceptions import DockerException

from .conftest import override_odoo_entrypoint, stop_project

fail_hosts = ["www.googleapis.com"]
allow_hosts = ["www.google.com"]


def curl_cmd(url):
    return ["curl"] + curl_args(url)


def curl_args(url):
    return [
        "-o",
        "/dev/null",
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "2",
        url,
    ]


def test_selective_proxy(
    cloned_template: Path,
    supported_odoo_version: float,
    single_project_path: Path,
):
    """Test that the selective access proxy actually works"""
    run_copy(
        str(cloned_template),
        str(single_project_path),
        data={
            "odoo_version": supported_odoo_version,
            "postgres_dbname": "devel",
            "whitelisted_hosts_devel": allow_hosts,
        },
        vcs_ref="HEAD",
        defaults=True,
        overwrite=True,
        unsafe=True,
    )
    stop_project(single_project_path)
    invoke("img-build")
    override_odoo_entrypoint(single_project_path)
    docker.compose.up(detach=True)
    for allowed_host in allow_hosts:
        # If no error is thrown, http get went right
        docker.compose.execute(
            service="odoo", command=curl_cmd(allowed_host), tty=False
        )
        docker.compose.run(
            service="odoo",
            entrypoint="curl",
            command=curl_args(allowed_host),
            tty=False,
        )
    for denied_host in fail_hosts:
        with pytest.raises(DockerException):
            docker.compose.execute(
                service="odoo",
                command=curl_cmd(denied_host),
                tty=False,
            )

        with pytest.raises(DockerException):
            docker.compose.run(
                service="odoo",
                entrypoint="curl",
                command=curl_args(denied_host),
                tty=False,
            )
