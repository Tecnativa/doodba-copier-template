from pathlib import Path
from shutil import rmtree

import pytest
import yaml
from copier.main import copy
from plumbum import local
from plumbum.cmd import git, invoke


def test_default_settings(
    tmp_path: Path, any_odoo_version: float, cloned_template: Path
):
    """Test that a template can be rendered from zero for each version."""
    with local.cwd(cloned_template):
        copy(
            ".",
            str(tmp_path),
            vcs_ref="test",
            force=True,
            data={"odoo_version": any_odoo_version},
        )
    with local.cwd(tmp_path):
        # TODO When copier runs pre-commit before extracting diff, make sure
        # here that it works as expected
        Path(tmp_path, "odoo", "auto", "addons").rmdir()
        Path(tmp_path, "odoo", "auto").rmdir()
        git("add", ".")
        git("commit", "-am", "Hello World", retcode=1)  # pre-commit fails
        git("commit", "-am", "Hello World")


def test_pre_commit_autoinstall(
    cloned_template: Path, tmp_path: Path, supported_odoo_version: float
):
    """Test that pre-commit is automatically (un)installed in alien repos.

    This test is slower because it has to download and build OCI images and
    download git code, so it's only executed against these Odoo versions:

    - 10.0 because it's Python 2 and has no pre-commit configurations in OCA.
    - 13.0 because it's Python 3 and has pre-commit configurations in OCA.
    """
    if supported_odoo_version not in {10.0, 13.0}:
        pytest.skip("this test is only tested with other odoo versions")
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"odoo_version": supported_odoo_version},
    )
    with local.cwd(tmp_path):
        with (tmp_path / "odoo" / "custom" / "src" / "addons.yaml").open("w") as fd:
            yaml.dump({"server-tools": "*"}, fd)
        # User can download git code from any folder
        with local.cwd(tmp_path / "odoo" / "custom" / "src" / "private"):
            invoke("git-aggregate")
        # Check pre-commit is properly (un)installed
        pre_commit_present = supported_odoo_version >= 13.0
        server_tools_git = (
            tmp_path / "odoo" / "custom" / "src" / "server-tools" / ".git"
        )
        assert server_tools_git.is_dir()
        assert (
            server_tools_git / "hooks" / "pre-commit"
        ).is_file() == pre_commit_present
    # Remove source code, it can use a lot of disk space
    rmtree(tmp_path)
