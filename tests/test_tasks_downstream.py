import re
import time
from pathlib import Path

import pytest
from copier import run_copy
from plumbum import ProcessExecutionError, local
from plumbum.cmd import invoke
from python_on_whales import DockerClient
from python_on_whales.exceptions import DockerException

from .conftest import (
    DBVER_PER_ODOO,
    build_file_tree,
    generate_test_addon,
    safe_stop_env,
    socket_is_open,
)


def _install_status(module):
    docker = DockerClient(compose_files=["devel.yaml"])
    return docker.compose.run(
        "odoo",
        command=[
            "psql",
            "-tc",
            f"select state from ir_module_module where name='{module}'",
        ],
        # envs={
        #     'LOG_LEVEL': 'WARNING',
        #     'PGDATABASE': dbname,
        # },
        remove=True,
        tty=False,
    ).strip()


def _get_config_param(key):
    docker = DockerClient(compose_files=["devel.yaml"])
    return docker.compose.run(
        "odoo",
        command=[
            "psql",
            "-tc",
            f"select value from ir_config_parameter where key='{key}'",
        ],
        # envs={
        #     'LOG_LEVEL': 'WARNING',
        #     'PGDATABASE': dbname,
        # },
        remove=True,
        tty=False,
    ).strip()


def _wait_for_test_to_start():
    docker = DockerClient(compose_files=["devel.yaml"])
    # Wait for test to start
    for _i in range(10):
        time.sleep(2)
        stdout = docker.compose.logs("odoo")
        if "Executing odoo --test-enable" in stdout:
            break
    return stdout


def _tests_ran(stdout, odoo_version, addon_name):
    # Ensure the addon was installed/updated, and not independent ones
    if odoo_version < 19:
        assert f"module {addon_name}: creating or updating database tables" in stdout
        # Ensure the addon was tested
        main_pkg, suffix = "odoo", r"\:\sStarting"
        if odoo_version < 13.0:
            suffix = r"\srunning tests."
        if odoo_version < 10.0:
            main_pkg = "openerp"
        assert re.search(
            rf"{main_pkg}\.addons\.{addon_name}\.tests\.\w+{suffix}", stdout
        )
        # Check no alien addons are installed, updated or tested
        if addon_name != "base":
            assert "module base: creating or updating database tables" not in stdout
            assert not re.search(
                rf"{main_pkg}\.addons\.base\.tests\.\w+{suffix}", stdout
            )
    else:
        assert any(
            mark in stdout
            for mark in (
                f"Installing module {addon_name}",
                f"odoo.addons.{addon_name}",
                "Running tests",
                "tests succeeded",
                "All tests passed",
                "odoo.sql_db: ConnectionPool",
            )
        )


@pytest.mark.sequential
def test_resetdb(
    cloned_template: Path,
    supported_odoo_version: float,
    tmp_path: Path,
):
    """Test the dropdb task.

    On this test flow, other downsream tasks are also tested:

    - img-build
    - git-aggregate
    - stop --purge
    - snapshot
    - restore-snapshot
    """
    try:
        with local.cwd(tmp_path):
            data = {
                "odoo_version": supported_odoo_version,
                "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
                "postgres_dbname": "devel",
            }
            run_copy(
                src_path=str(cloned_template),
                data=data,
                vcs_ref="HEAD",
                defaults=True,
                overwrite=True,
                unsafe=True,
            )
            # Imagine the user is in the src subfolder for these tasks
            with local.cwd(tmp_path / "odoo" / "custom" / "src"):
                invoke("img-build")
                invoke("git-aggregate")
            # No ir_module_module table exists yet
            with pytest.raises(DockerException):
                _install_status("base")
            # Imagine the user is in the odoo subrepo for these tasks
            with local.cwd(tmp_path / "odoo" / "custom" / "src" / "odoo"):
                # This should install just "base"
                stdout = invoke("resetdb", "--no-populate")
            if supported_odoo_version < 19:
                assert "Creating database cache" in stdout
                assert "from template devel" in stdout
            else:
                assert "odoo.sql_db: ConnectionPool" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "uninstalled"
            assert _install_status("sale") == "uninstalled"
            assert not _get_config_param("report.url")
            # Install "purchase"
            stdout = invoke("resetdb", "-m", "purchase")
            if supported_odoo_version < 19:
                assert "Creating database cache" in stdout
                assert "from template devel" in stdout
            else:
                assert "odoo.sql_db: ConnectionPool" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "installed"
            assert _install_status("sale") == "uninstalled"
            # Install "sale" in a separate database
            stdout = invoke("resetdb", "-m", "sale", "-d", "sale_only")
            if supported_odoo_version < 19:
                assert "Creating database cache" in stdout
                assert "from template sale_only" in stdout
            else:
                assert "odoo.sql_db: ConnectionPool" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "installed"
            assert _install_status("sale") == "uninstalled"
            # FIXME: See https://github.com/gabrieldemarmiesse/python-on-whales/pull/380
            # assert _install_status("base", "sale_only") == "installed"
            # assert _install_status("purchase", "sale_only") == "uninstalled"
            # assert _install_status("sale", "sale_only") == "installed"
            # Install "sale" in main database
            stdout = invoke("resetdb", "-m", "sale")
            if supported_odoo_version < 19:
                assert "Creating database devel from template cache" in stdout
                assert "Found matching database template" in stdout
            else:
                assert "odoo.sql_db: ConnectionPool" in stdout
            assert _install_status("base") == "installed"
            assert _install_status("purchase") == "uninstalled"
            assert _install_status("sale") == "installed"
            # Snapshot current DB
            invoke("snapshot", "--destination-db", "db_with_sale")
            if supported_odoo_version >= 11:
                invoke("preparedb")
                assert _get_config_param("report.url") == "http://localhost:8069"
                stdout = invoke("resetdb")  # --populate default
                # report.url should be set in the DB
                assert _get_config_param("report.url") == "http://localhost:8069"
            else:
                invoke(
                    "resetdb"
                )  # Despite new default --populate, shouldn't introduce error
                with pytest.raises(ProcessExecutionError):
                    invoke("preparedb")
            # DB should now be reset
            assert _install_status("sale") == "uninstalled"
            # Restore snapshot
            invoke("restore-snapshot", "--snapshot-name", "db_with_sale")
            assert _install_status("sale") == "installed"
    finally:
        safe_stop_env(tmp_path / "odoo" / "custom" / "src" / "odoo")


@pytest.mark.sequential
def test_start(
    cloned_template: Path,
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
            data = {
                "odoo_version": supported_odoo_version,
                "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
                "postgres_dbname": "devel",
            }
            run_copy(
                src_path=str(cloned_template),
                data=data,
                vcs_ref="HEAD",
                defaults=True,
                overwrite=True,
                unsafe=True,
            )
            # Imagine the user is in the src subfolder for these tasks
            with local.cwd(tmp_path / "odoo" / "custom" / "src"):
                invoke("img-build")
                stdout = invoke("git-aggregate")
            # Test normal call
            print(stdout)
            assert "Reinitialized existing Git repository" in stdout
            assert "pre-commit installed" in stdout
            invoke("start")
            # Test "--debugpy and wait time call
            safe_stop_env(tmp_path)
            stdout = invoke("start", "--debugpy")
            assert socket_is_open("127.0.0.1", int(supported_odoo_version) * 1000 + 899)
            # Check if auto-reload is disabled
            docker = DockerClient()
            container_logs = docker.compose.logs("odoo")
            assert "dev=reload" not in container_logs
    finally:
        safe_stop_env(
            tmp_path,
        )


@pytest.mark.sequential
def test_install_test(
    cloned_template: Path,
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
            data = {
                "odoo_version": supported_odoo_version,
                "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
            }
            run_copy(
                src_path=str(cloned_template),
                data=data,
                vcs_ref="HEAD",
                defaults=True,
                overwrite=True,
                unsafe=True,
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
            # Test "note" or "project_todo" simple call in init mode (default)
            module_name = "note" if supported_odoo_version < 17 else "project_todo"
            assert _install_status(module_name) == "uninstalled"
            stdout = invoke("test", "-m", module_name, "--mode", "init", retcode=None)
            # Ensure module was installed and tests ran
            assert _install_status(module_name) == "installed"
            _tests_ran(stdout, supported_odoo_version, module_name)
            # Test module simple call in update mode
            stdout = invoke("test", "-m", module_name, "--mode", "update", retcode=None)
            _tests_ran(stdout, supported_odoo_version, module_name)
            # Change to subfolder and test
            with local.cwd(
                tmp_path / "odoo" / "custom" / "src" / "odoo" / "addons" / module_name
            ):
                # Test module based on current folder
                stdout = invoke("test", retcode=None)
                _tests_ran(stdout, supported_odoo_version, module_name)
            # Test --debugpy and wait time call with
            safe_stop_env(tmp_path, purge=False)
            invoke("test", "-m", module_name, "--debugpy", retcode=None)
            assert socket_is_open("127.0.0.1", int(supported_odoo_version) * 1000 + 899)
            stdout = _wait_for_test_to_start()
            assert "python -m debugpy" in stdout
    finally:
        safe_stop_env(
            tmp_path,
        )


@pytest.mark.sequential
@pytest.mark.skip_for_prereleases
def test_test_tasks(
    cloned_template: Path,
    supported_odoo_version: float,
    tmp_path: Path,
):
    """Test the tasks associated with the Odoo test flow.

    On this test flow, the following tasks are tested:

    - img-build
    - git-aggregate
    - stop --purge
    - resetdb --dependencies
    - test [options]

    This test will be skipped for prereleased versions of Doodba
    """
    try:
        with local.cwd(tmp_path):
            data = {
                "odoo_version": supported_odoo_version,
                "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
            }
            run_copy(
                src_path=str(cloned_template),
                data=data,
                vcs_ref="HEAD",
                defaults=True,
                overwrite=True,
                unsafe=True,
            )
            # Imagine the user is in the src subfolder for these tasks
            # and the DB is clean
            with local.cwd(tmp_path / "odoo" / "custom" / "src"):
                invoke("img-build")
                invoke("git-aggregate")
            module_name = "note" if supported_odoo_version < 17 else "project_todo"
            # Prepare environment with "note" or "project_todo" dependencies
            invoke("resetdb", "-m", module_name, "--dependencies")
            assert _install_status("mail") == "installed"
            # Test module simple call in init mode (default)
            if supported_odoo_version >= 17:
                # Uninstall module
                invoke("uninstall", "-m", module_name)
            assert _install_status(module_name) == "uninstalled"
            stdout = invoke("test", "-m", module_name, retcode=None)
            # Ensure module was installed and tests ran
            assert _install_status(module_name) == "installed"
            _tests_ran(stdout, supported_odoo_version, module_name)
            if supported_odoo_version >= 11:
                # Prepare environment for all private addons and "test" them
                with local.cwd(tmp_path / "odoo" / "custom" / "src" / "private"):
                    generate_test_addon(
                        "test_module", supported_odoo_version, dependencies='["mail"]'
                    )
                invoke("resetdb", "--private", "--dependencies")
                assert _install_status("mail") == "installed"
                # Test "test_module" simple call in init mode (default)
                assert _install_status("test_module") == "uninstalled"
                stdout = invoke("test", "--private", retcode=None)
                # Ensure "test_module" was installed and tests ran
                assert _install_status("test_module") == "installed"
                # Prepare environment for OCA addons and test them
                with local.cwd(tmp_path / "odoo" / "custom" / "src"):
                    build_file_tree(
                        {
                            "addons.yaml": """\
                            account-invoicing:
                                - account_invoice_refund_link
                        """,
                        }
                    )
                invoke("git-aggregate")
                if supported_odoo_version < 18.0:
                    # TODO: Put 19.0 once 'account_invoice_refund_link' is migrated to Odoo 18.0
                    # Skip the tests for 'account_invoice_refund_link' as it's not available yet
                    invoke("resetdb", "--extra", "--private", "--dependencies")
                    assert (
                        _install_status("mail") == "installed"
                    )  # dependency of test_module
                    assert (
                        _install_status("account") == "installed"
                    )  # dependency of account_invoice_refund_link
                    # Test "account_invoice_refund_link"
                    assert _install_status("test_module") == "uninstalled"
                    assert (
                        _install_status("account_invoice_refund_link") == "uninstalled"
                    )
                    stdout = invoke("test", "--private", "--extra", retcode=None)
                    # Ensure "test_module" and "account_invoice_refund_link" were installed
                    assert _install_status("test_module") == "installed"
                    assert _install_status("account_invoice_refund_link") == "installed"
                    _tests_ran(
                        stdout, supported_odoo_version, "account_invoice_refund_link"
                    )
            # Test --test-tags
            if supported_odoo_version >= 12 and supported_odoo_version < 18.0:
                # TODO: Put 19.0 once 'account_invoice_refund_link' is migrated to Odoo 18.0
                # Skip the tests for 'account_invoice_refund_link' as it's not available yet
                with local.cwd(tmp_path / "odoo" / "custom" / "src" / "private"):
                    generate_test_addon(
                        "test_module",
                        supported_odoo_version,
                        dependencies='["account_invoice_refund_link"]',
                    )
                # Run again but skip tests
                invoke("resetdb", "--extra", "--private", "--dependencies")
                stdout = invoke(
                    "test",
                    "--private",
                    "--extra",
                    "--skip",
                    "account_invoice_refund_link",
                    retcode=None,
                )
                assert _install_status("test_module") == "installed"
                assert _install_status("account_invoice_refund_link") == "installed"
                # Tests for account_invoice_refund_link should not run
                with pytest.raises(AssertionError):
                    _tests_ran(
                        stdout,
                        supported_odoo_version,
                        "account_invoice_refund_link",
                    )
    finally:
        safe_stop_env(
            tmp_path,
        )
