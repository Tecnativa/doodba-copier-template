import logging
import os
import shutil
import socket
import stat
import tempfile
import textwrap
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Union

import pytest
import yaml
from plumbum import ProcessExecutionError, local
from plumbum.cmd import git, invoke
from python_on_whales import DockerClient

_logger = logging.getLogger(__name__)

with open("copier.yml") as copier_fd:
    COPIER_SETTINGS = yaml.safe_load(copier_fd)

# Different tests test different Odoo versions
OLDEST_SUPPORTED_ODOO_VERSION = 11.0
ALL_ODOO_VERSIONS = tuple(COPIER_SETTINGS["odoo_version"]["choices"])
TRAEFIK_VERSION = os.getenv("TRAEFIK_VERSION", "3")

SUPPORTED_ODOO_VERSIONS = tuple(
    v for v in ALL_ODOO_VERSIONS if v >= OLDEST_SUPPORTED_ODOO_VERSION
)
LAST_ODOO_VERSION = max(SUPPORTED_ODOO_VERSIONS)
SELECTED_ODOO_VERSIONS = (
    frozenset(map(float, os.environ.get("SELECTED_ODOO_VERSIONS", "").split()))
    or ALL_ODOO_VERSIONS
)
PRERELEASE_ODOO_VERSIONS = {19.0}

# Postgres versions
ALL_PSQL_VERSIONS = tuple(COPIER_SETTINGS["postgres_version"]["choices"])
LATEST_PSQL_VER = ALL_PSQL_VERSIONS[-1]
DBVER_PER_ODOO = {
    11.0: {
        "oldest": "10",  # Odoo supports 9.6, but that version is not supported by the backup service and is necessary to be able to perform all tests
        "latest": "13",  # DB Authentication method limitation
    },
    12.0: {
        "oldest": "10",  # Odoo supports 9.6, but that version is not supported by the backup service and is necessary to be able to perform all tests
        "latest": "13",
    },
    13.0: {
        "oldest": "10",  # Odoo supports 9.6, but that version is not supported by the backup service and is necessary to be able to perform all tests
        "latest": "16",
    },
    14.0: {
        "oldest": "10",
        "latest": "16",
    },
    15.0: {
        "oldest": "10",
        "latest": LATEST_PSQL_VER,
    },
    16.0: {
        "oldest": "12",
        "latest": LATEST_PSQL_VER,
    },
    17.0: {
        "oldest": "12",
        "latest": LATEST_PSQL_VER,
    },
    18.0: {
        "oldest": "12",
        "latest": LATEST_PSQL_VER,
    },
    19.0: {
        "oldest": "12",
        "latest": LATEST_PSQL_VER,
    },
}


@pytest.fixture(autouse=True)
def skip_odoo_prereleases(supported_odoo_version: float, request):
    """Fixture to automatically skip tests for prereleased odoo versions."""
    if (
        request.node.get_closest_marker("skip_for_prereleases")
        and supported_odoo_version in PRERELEASE_ODOO_VERSIONS
    ):
        pytest.skip(
            f"skipping tests for prereleased odoo version {supported_odoo_version}"
        )


def pytest_addoption(parser):
    parser.addoption(
        "--skip-docker-tests",
        action="store_true",
        default=False,
        help="Skip Docker tests",
    )


@pytest.fixture(params=ALL_ODOO_VERSIONS)
def any_odoo_version(request) -> float:
    """Returns any usable odoo version."""
    if request.param not in SELECTED_ODOO_VERSIONS:
        pytest.skip("odoo version not in selected range")
    return request.param


@pytest.fixture(params=SUPPORTED_ODOO_VERSIONS)
def supported_odoo_version(request) -> float:
    """Returns any usable odoo version."""
    if request.param not in SELECTED_ODOO_VERSIONS:
        pytest.skip("supported odoo version not in selected range")
    return request.param


@pytest.fixture()
def cloned_template():
    """This repo cloned to a temporary destination.

    The clone will include dirty changes, and it will have a 'test' tag in its HEAD.

    It returns the local `Path` to the clone.
    """
    patches = [git("diff", "--cached"), git("diff")]
    with tempfile.TemporaryDirectory("_cloned_template") as dirty_template_clone:
        git("clone", ".", dirty_template_clone)
        with local.cwd(dirty_template_clone):
            git("config", "commit.gpgsign", "false")
            for patch in patches:
                if patch:
                    (git["apply", "--reject"] << patch)()
                    git("add", ".")
                    git(
                        "commit",
                        "--author=Test<test@test>",
                        "--message=dirty changes",
                        "--no-verify",
                    )
            git("tag", "--force", "test")
        yield dirty_template_clone


@pytest.fixture()
def versionless_odoo_autoskip(request):
    """Fixture to automatically skip tests when testing for older odoo versions."""
    is_version_specific_test = (
        "any_odoo_version" in request.fixturenames
        or "supported_odoo_version" in request.fixturenames
    )
    if LAST_ODOO_VERSION not in SELECTED_ODOO_VERSIONS and not is_version_specific_test:
        pytest.skip("version-independent test in old versioned odoo test session")


@pytest.fixture(params=TRAEFIK_VERSION)
def traefik_host(request):
    """Fixture to indicate where to find a running traefik instance."""
    docker = DockerClient()
    if request.param == "3":
        traefik_container = docker.run(
            "traefik:v3.1.2",
            detach=True,
            privileged=True,
            networks=["inverseproxy_shared"],
            volumes=[("/var/run/docker.sock", "/var/run/docker.sock", "ro")],
            command=[
                "--accessLog=true",
                "--entryPoints.web-alt.address=:8080",
                "--entryPoints.web-insecure.address=:80",
                "--entryPoints.web-main.address=:443",
                "--log.level=debug",
                "--providers.docker.exposedByDefault=false",
                "--providers.docker.network=inverseproxy_shared",
                "--providers.docker=true",
            ],
        )
    elif request.param == "2":
        traefik_container = docker.run(
            "traefik:v2.4",
            detach=True,
            privileged=True,
            networks=["inverseproxy_shared"],
            volumes=[("/var/run/docker.sock", "/var/run/docker.sock", "ro")],
            command=[
                "--accessLog=true",
                "--entrypoints.web-alt.address=:8080",
                "--entrypoints.web-insecure.address=:80",
                "--entrypoints.web-main.address=:443",
                "--log.level=debug",
                "--providers.docker.exposedByDefault=false",
                "--providers.docker.network=inverseproxy_shared",
                "--providers.docker=true",
            ],
        )
    else:
        traefik_container = docker.run(
            "traefik:v1.7",
            detach=True,
            privileged=True,
            networks=["inverseproxy_shared"],
            volumes=[("/var/run/docker.sock", "/var/run/docker.sock", "ro")],
            command=[
                "--defaultEntryPoints=web-insecure,web-main",
                "--docker.exposedByDefault=false",
                "--docker.watch",
                "--docker",
                "--entryPoints=Name:web-alt Address::8080 Compress:on",
                "--entryPoints=Name:web-insecure Address::80 Redirect.EntryPoint:web-main",
                "--entryPoints=Name:web-main Address::443 Compress:on TLS TLS.minVersion:VersionTLS12",
                "--logLevel=debug",
            ],
        )
    interesting_details = {
        "ip": traefik_container.network_settings.networks[
            "inverseproxy_shared"
        ].ip_address,
        "traefik_version": traefik_container.config.labels[
            "org.opencontainers.image.version"
        ],
        "traefik_image": traefik_container.config.image,
    }
    interesting_details["hostname"] = f"{interesting_details['ip']}.sslip.io"
    yield interesting_details
    # Make sure there were no errors or warnings in logs
    traefik_logs = docker.logs(traefik_container)
    docker.remove(traefik_container, force=True)
    assert " level=error " not in traefik_logs
    assert " level=warn " not in traefik_logs


def teardown_function(function):
    pre_commit_log = (
        Path("~") / ".cache" / "pre-commit" / "pre-commit.log"
    ).expanduser()
    if pre_commit_log.is_file():
        print(pre_commit_log.read_text())
        pre_commit_log.unlink()


# Helpers
def build_file_tree(spec: Dict[Union[str, Path], str], dedent: bool = True):
    """Builds a file tree based on the received spec."""
    for path, contents in spec.items():
        path = Path(path)
        if dedent:
            contents = textwrap.dedent(contents)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as fd:
            fd.write(contents)


def socket_is_open(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sock.connect_ex((host, port)) == 0:
        return True
    return False


def generate_test_addon(
    addon_name, odoo_version, installable=True, ugly=False, dependencies=None
):
    """Generates a simple addon for testing
    Can be an ugly addon to trigger pre-commit formatting
    """
    is_py3 = odoo_version >= 11
    manifest = "__manifest__" if is_py3 else "__openerp__"
    file_tree = {
        f"{addon_name}/__init__.py": """\
            from . import models
        """,
        f"{addon_name}/models/__init__.py": """\
            from . import res_partner
        """,
    }
    if ugly:
        file_tree.update(
            {
                f"{addon_name}/{manifest}.py": f"""\
                    {"{"}
                    'name':"{addon_name}",'license':'AGPL-3',
                    'version':'{odoo_version}.1.0.0',
                    'depends': {dependencies or '["base"]'},
                    'installable': {installable},
                    'auto_install': False,
                    'author': 'Tecnativa',
                    {"}"}
                """,
                f"{addon_name}/models/res_partner.py": """\
                    from odoo import models;from os.path import join;
                    from requests import get
                    from logging import getLogger
                    import io,sys,odoo
                    _logger=getLogger(__name__)
                    class ResPartner(models.Model):
                        _inherit='res.partner'
                        def some_method(self,test):
                            '''some weird
                                docstring'''
                            _logger.info(models,join,get,io,sys,odoo)
                """,
                f"{addon_name}/README.rst": "",
                f"{addon_name}/readme/DESCRIPTION.rst": addon_name,
            }
        )
    else:
        file_tree.update(
            {
                f"{addon_name}/{manifest}.py": f"""\
                    {"{"}
                        "name": "{addon_name}",
                        "license": "AGPL-3",
                        "version": "{odoo_version}.1.0.0",
                        "depends": {dependencies or '["base"]'},
                        "installable": {installable},
                        "auto_install": False,
                        "author": "Tecnativa",
                    {"}"}
                """,
                f"{addon_name}/models/res_partner.py": '''\
                    import io
                    import sys
                    from logging import getLogger
                    from os.path import join

                    from requests import get

                    import odoo
                    from odoo import models

                    _logger = getLogger(__name__)


                    class ResPartner(models.Model):
                        _inherit = "res.partner"

                        def some_method(self, test):
                            """some weird
                            docstring"""
                            _logger.info(models, join, get, io, sys, odoo)
                ''',
            }
        )
    build_file_tree(file_tree)


def _containers_running(exec_path):
    with local.cwd(exec_path):
        docker = DockerClient()
        containers_list = docker.container.list(all=True)
        if len(containers_list) > 0:
            _logger.error(containers_list)
            return True
        return False


def safe_stop_env(exec_path, purge=True):
    with local.cwd(exec_path):
        try:
            args = ["stop"]
            if purge:
                args.append("--purge")
            invoke.run(args)
        except ProcessExecutionError as e:
            if (
                "has active endpoints" not in e.stderr
                and "has active endpoints" not in e.stdout
            ):
                raise e
            assert not _containers_running(
                exec_path
            ), "Containers running or not removed. 'stop [--purge]' command did not work."


@contextmanager
def bypass_pre_commit():
    """A context manager to patch the pre-commit binary to ignore it"""
    pre_commit_path_str = shutil.which("pre-commit")
    try:
        # Move current binary to different location
        pre_commit_path = Path(pre_commit_path_str)
        shutil.move(pre_commit_path_str, pre_commit_path_str + "-old")
        with pre_commit_path.open("w") as fd:
            fd.write(
                "#!/usr/bin/python3\n"
                "# -*- coding: utf-8 -*-\n"
                "import sys\n"
                "if __name__ == '__main__':\n"
                "    sys.exit(0)\n"
            )
        cur_stat = pre_commit_path.stat()
        # Like chmod ug+x
        pre_commit_path.chmod(cur_stat.st_mode | stat.S_IXUSR | stat.S_IXGRP)
        yield
    finally:
        # Restore original binary
        shutil.move(pre_commit_path_str + "-old", pre_commit_path_str)
