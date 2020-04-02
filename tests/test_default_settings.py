from pathlib import Path
from shutil import rmtree

import pytest
import yaml
from copier.main import copy
from plumbum import local
from plumbum.cmd import diff, git, invoke, pre_commit

from .helpers import ALL_ODOO_VERSIONS, clone_self_dirty


@pytest.mark.parametrize("odoo_version", ALL_ODOO_VERSIONS)
def test_default_settings(tmp_path: Path, odoo_version: float):
    """Test that a template rendered from zero is OK for each version.

    No params are given apart from odoo_version. This tests that scaffoldings
    render fine with default answers.
    """
    src, dst = tmp_path / "src", tmp_path / "dst"
    clone_self_dirty(src)
    with local.cwd(src):
        copy(
            ".",
            str(dst),
            vcs_ref="test",
            force=True,
            data={"odoo_version": odoo_version},
        )
    with local.cwd(dst):
        git("add", ".")
        pre_commit("run", "-a", retcode=None)
        git("commit", "-am", "Hello World")
    # The result matches what we expect
    diff(
        "--context=3",
        "--exclude=.git",
        "--recursive",
        local.cwd / "tests" / "default_settings" / f"v{odoo_version:.1f}",
        dst,
    )


@pytest.mark.parametrize("odoo_version", (10.0, 13.0))
def test_pre_commit_autoinstall(tmp_path: Path, odoo_version: float):
    """Test that pre-commit is automatically (un)installed in alien repos.

    This test is slower because it has to download and build OCI images and
    download git code, so it's only executed against these Odoo versions:

    - 10.0 because it's Python 2 and has no pre-commit configurations in OCA.
    - 13.0 because it's Python 3 and has pre-commit configurations in OCA.
    """
    copy(
        ".",
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"odoo_version": odoo_version},
    )
    with local.cwd(tmp_path):
        with (tmp_path / "odoo" / "custom" / "src" / "addons.yaml").open("w") as fd:
            yaml.dump({"server-tools": "*"}, fd)
        # User can download git code
        invoke("git-aggregate")
        # Check pre-commit is properly (un)installed
        pre_commit_present = odoo_version >= 13.0
        server_tools_git = (
            tmp_path / "odoo" / "custom" / "src" / "server-tools" / ".git"
        )
        assert server_tools_git.is_dir()
        assert (
            server_tools_git / "hooks" / "pre-commit"
        ).is_file() == pre_commit_present
    # Remove source code, it can use a lot of disk space
    rmtree(tmp_path)
