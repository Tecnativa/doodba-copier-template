"""Nitpicking small tests ahead."""
import pytest
from copier.main import copy

from .helpers import clone_self_dirty

WHITESPACE_PREFIXED_LICENSES = (
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "LGPL-3.0-or-later",
)


@pytest.mark.parametrize("project_license", WHITESPACE_PREFIXED_LICENSES)
def test_license_whitespace_prefix(tmpdir, project_license):
    src, dst = tmpdir / "src", tmpdir / "dst"
    clone_self_dirty(src)
    copy(
        str(src),
        str(dst),
        vcs_ref="test",
        force=True,
        data={"project_license": project_license},
    )
    assert (dst / "LICENSE").read().startswith("   ")
