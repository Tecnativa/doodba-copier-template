"""Nitpicking small tests ahead."""
from pathlib import Path

import pytest
from copier.main import copy
from plumbum import local
from plumbum.cmd import git

from .helpers import clone_self_dirty

WHITESPACE_PREFIXED_LICENSES = (
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "LGPL-3.0-or-later",
)


@pytest.mark.parametrize("project_license", WHITESPACE_PREFIXED_LICENSES)
def test_license_whitespace_prefix(tmp_path: Path, project_license):
    src, dst = tmp_path / "src", tmp_path / "dst"
    clone_self_dirty(src)
    copy(
        str(src),
        str(dst),
        vcs_ref="test",
        force=True,
        data={"project_license": project_license},
    )
    assert (dst / "LICENSE").read_text().startswith("   ")


def test_no_vscode_in_private(tmp_path: Path):
    """Make sure .vscode folders are git-ignored in private folder."""
    copy(".", str(tmp_path), vcs_ref="HEAD", force=True)
    with local.cwd(tmp_path):
        git("add", ".")
        git("commit", "-am", "hello world")
        vscode = tmp_path / "odoo" / "custom" / "src" / "private" / ".vscode"
        vscode.mkdir()
        (vscode / "something").touch()
        assert not git("status", "--porcelain")
