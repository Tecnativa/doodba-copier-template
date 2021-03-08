import logging
import re
import time
from pathlib import Path

import pytest
from copier import copy
from plumbum import ProcessExecutionError, local
from plumbum.cmd import docker_compose, invoke
from plumbum.machines.local import LocalCommand

from .conftest import safe_stop_env, socket_is_open

_logger = logging.getLogger(__name__)


def _install_status(module, dbname="devel"):
    return docker_compose(
        "run",
        "--rm",
        "-e",
        "LOG_LEVEL=WARNING",
        "-e",
        f"PGDATABASE={dbname}",
        "odoo",
        "psql",
        "-tc",
        f"select state from ir_module_module where name='{module}'",
    ).strip()


def _wait_for_test_to_start():
    # Wait for test to start
    for _i in range(10):
        time.sleep(2)
        _ret_code, stdout, _stderr = docker_compose.run(("logs", "odoo"))
        if "Executing odoo --test-enable" in stdout:
            break
    return stdout


def _tests_ran(stdout, odoo_version, addon_name):
    # Ensure the addon was installed/updated, and not independent ones
    assert f"module {addon_name}: creating or updating database tables" in stdout
    # Ensure the addon was tested
    main_pkg, suffix = "odoo", r"\:\sStarting"
    if odoo_version < 13.0:
        suffix = r"\srunning tests."
    if odoo_version < 10.0:
        main_pkg = "openerp"
    assert re.search(fr"{main_pkg}\.addons\.{addon_name}\.tests\.\w+{suffix}", stdout)
    # Check no alien addons are installed, updated or tested
    if addon_name != "base":
        assert "module base: creating or updating database tables" not in stdout
        assert not re.search(fr"{main_pkg}\.addons\.base\.tests\.\w+{suffix}", stdout)


@pytest.mark.sequential
def test_resetdb(
    cloned_template: Path,
    docker: LocalCommand,
    supported_odoo_version: float,
    tmp_path: Path,
):
    """Test the dropdb task.

    On this test flow, other downsream tasks are also tested:

    - img-build
    - git-aggregate
    - stop --purge
    """
    try:
        with local.cwd(tmp_path):
            copy(
                src_path=str(cloned_template),
                vcs_ref="HEAD",
                force=True,
                data={"odoo_version": supported_odoo_version},
            )
            # Imagine the user is in the src subfolder for these tasks
            with local.cwd(tmp_path / "odoo" / "custom" / "src"):
                invoke("img-build")
                invoke("git-aggregate")
            # No ir_module_module table exists yet
            with pytest.raises(ProcessExecutionError):
                _install_status("base")
            # Imagine the user is in the odoo subrepo for these tasks
            with local.cwd(tmp_path / "odoo" / "custom" / "src" / "odoo"):
                # This should install just "base"
                stdout = invoke("resetdb")
            assert "Creating database cache" in stdout
            assert "from template devel" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "uninstalled"
            assert _install_status("sale") == "uninstalled"
            # Install "purchase"
            stdout = invoke("resetdb", "-m", "purchase")
            assert "Creating database cache" in stdout
            assert "from template devel" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "installed"
            assert _install_status("sale") == "uninstalled"
            # Install "sale" in a separate database
            stdout = invoke("resetdb", "-m", "sale", "-d", "sale_only")
            assert "Creating database cache" in stdout
            assert "from template sale_only" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "installed"
            assert _install_status("sale") == "uninstalled"
            assert _install_status("base", "sale_only") == "installed"
            assert _install_status("purchase", "sale_only") == "uninstalled"
            assert _install_status("sale", "sale_only") == "installed"
            # Install "sale" in main database
            stdout = invoke("resetdb", "-m", "sale")
            assert "Creating database devel from template cache" in stdout
            assert "Found matching database template" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "uninstalled"
            assert _install_status("sale") == "installed"
    finally:
        safe_stop_env(
            tmp_path / "odoo" / "custom" / "src" / "odoo",
        )


@pytest.mark.sequential
def test_start(
    cloned_template: Path,
    docker: LocalCommand,
    supported_odoo_version: float,
    tmp_path: Path,
):
    """Test the start task.

    On this test flow, other downsream tasks are also tested:

    - img-build
    - git-aggregate
    - stop --purge
    """
    try:
        with local.cwd(tmp_path):
            copy(
                src_path=str(cloned_template),
                vcs_ref="HEAD",
                force=True,
                data={"odoo_version": supported_odoo_version},
            )
            # Imagine the user is in the src subfolder for these tasks
            with local.cwd(tmp_path / "odoo" / "custom" / "src"):
                invoke("img-build")
                invoke("git-aggregate")
            # Test normal call
            stdout = invoke("start")
            print(stdout)
            assert "Reinitialized existing Git repository" in stdout
            assert "pre-commit installed" in stdout
            # Test "--debugpy and wait time call
            invoke("stop")
            stdout = invoke("start", "--debugpy")
            assert socket_is_open("127.0.0.1", int(supported_odoo_version) * 1000 + 899)
            # Check if auto-reload is disabled
            container_logs = docker_compose("logs", "odoo")
            assert "dev=reload" not in container_logs
    finally:
        safe_stop_env(
            tmp_path,
        )


@pytest.mark.sequential
def test_install_test(
    cloned_template: Path,
    docker: LocalCommand,
    supported_odoo_version: float,
    tmp_path: Path,
):
    """Test the install and test tasks.

    On this test flow, other downsream tasks are also tested:

    - img-build
    - git-aggregate
    - stop --purge
    """
    try:
        with local.cwd(tmp_path):
            copy(
                src_path=str(cloned_template),
                vcs_ref="HEAD",
                force=True,
                data={"odoo_version": supported_odoo_version},
            )
            # Imagine the user is in the src subfolder for these tasks
            # and the DB is clean
            with local.cwd(tmp_path / "odoo" / "custom" / "src"):
                invoke("img-build")
                invoke("git-aggregate")
                invoke("resetdb")
            # Install "mail"
            assert _install_status("mail") == "uninstalled"
            stdout = invoke("install", "-m", "mail")
            assert _install_status("mail") == "installed"
            if supported_odoo_version > 8:
                assert _install_status("utm") == "uninstalled"
                # Change to "utm" subfolder and install
                with local.cwd(
                    tmp_path / "odoo" / "custom" / "src" / "odoo" / "addons" / "utm"
                ):
                    # Install "utm" based on current folder
                    stdout = invoke("install")
                assert _install_status("mail") == "installed"
                assert _install_status("utm") == "installed"
            # Test "note" simple call in init mode (default)
            assert _install_status("note") == "uninstalled"
            stdout = invoke("test", "-m", "note", "--mode", "init", retcode=None)
            # Ensure "note" was installed and tests ran
            assert _install_status("note") == "installed"
            _tests_ran(stdout, supported_odoo_version, "note")
            # Test "note" simple call in update mode
            stdout = invoke("test", "-m", "note", "--mode", "update", retcode=None)
            _tests_ran(stdout, supported_odoo_version, "note")
            # Change to "note" subfolder and test
            with local.cwd(
                tmp_path / "odoo" / "custom" / "src" / "odoo" / "addons" / "note"
            ):
                # Test "note" based on current folder
                stdout = invoke("test", retcode=None)
                _tests_ran(stdout, supported_odoo_version, "note")
            # Test --debugpy and wait time call with
            invoke("stop")
            invoke("test", "-m", "note", "--debugpy", retcode=None)
            assert socket_is_open("127.0.0.1", int(supported_odoo_version) * 1000 + 899)
            stdout = _wait_for_test_to_start()
            assert "python -m debugpy" in stdout
    finally:
        safe_stop_env(
            tmp_path,
        )
