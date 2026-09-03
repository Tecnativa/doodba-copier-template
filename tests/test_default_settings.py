from pathlib import Path

import pytest
import yaml
from plumbum import local
from plumbum.cmd import git, invoke

from .conftest import SharedTemplate


class TestDefaultSettings(SharedTemplate):
    def test_default_settings(
        self,
        cloned_project: Path,
    ):
        """Test that a template can be rendered from zero for each version."""

        # TODO When copier runs pre-commit before extracting diff, make sure
        # here that it works as expected
        Path(cloned_project, "odoo", "auto", "addons").rmdir()
        Path(cloned_project, "odoo", "auto").rmdir()
        git("add", ".")
        local["pre-commit"]("run", "--all-files", "--show-diff-on-failure", retcode=1)
        git("commit", "-am", "Hello World")

    def test_pre_commit_autoinstall(
        self, cloned_project: Path, supported_odoo_version: float
    ):
        """Test that pre-commit is automatically (un)installed in alien repos.

        This test is slower because it has to download and build OCI images and
        download git code, so it's only executed against these Odoo versions:

        - 10.0 because it's Python 2 and has no pre-commit configurations in OCA.
        - 13.0 because it's Python 3 and has pre-commit configurations in OCA.
        """
        if supported_odoo_version not in {10.0, 13.0}:
            pytest.skip("this test is only tested with other odoo versions")
        with (cloned_project / "odoo" / "custom" / "src" / "addons.yaml").open(
            "w"
        ) as fd:
            yaml.dump({"server-tools": "*"}, fd)
        # User can download git code from any folder
        with local.cwd(cloned_project / "odoo" / "custom" / "src" / "private"):
            invoke("git-aggregate")
        # Check pre-commit is properly (un)installed
        pre_commit_present = supported_odoo_version >= 13.0
        server_tools_git = (
            cloned_project / "odoo" / "custom" / "src" / "server-tools" / ".git"
        )
        assert server_tools_git.is_dir()
        assert (
            server_tools_git / "hooks" / "pre-commit"
        ).is_file() == pre_commit_present
