import os
from pathlib import Path

import pytest
from copier import copy
from plumbum import ProcessExecutionError, local
from plumbum.cmd import docker_compose, invoke


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


@pytest.mark.skipif(
    os.environ.get("DOCKER_TEST") != "1", reason="Missing DOCKER_TEST=1 env variable"
)
def test_resetdb(tmp_path: Path, cloned_template: Path, supported_odoo_version: float):
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
                # This should install just "base
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
        # Imagine the user is in the odoo subrepo for this command
        with local.cwd(tmp_path / "odoo" / "custom" / "src" / "odoo"):
            invoke("stop", "--purge")
