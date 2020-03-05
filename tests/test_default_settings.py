import pytest
from copier.main import copy
from plumbum import local
from plumbum.cmd import diff

from .helpers import ALL_ODOO_VERSIONS, clone_self_dirty


@pytest.mark.parametrize("odoo_version", ALL_ODOO_VERSIONS)
def test_default_settings(tmpdir, odoo_version):
    """Test that a template rendered from zero is OK for each version.

    No params are given apart from odoo_version. This tests that scaffoldings
    render fine with default answers.
    """
    src, dst = tmpdir / "src", tmpdir / "dst"
    clone_self_dirty(src)
    with local.cwd(src):
        copy(
            ".",
            str(dst),
            vcs_ref="test",
            force=True,
            data={"odoo_version": odoo_version},
        )
    diff(
        "--context=3",
        "--exclude=.git",
        "--recursive",
        local.cwd / "tests" / "default_settings" / f"v{odoo_version:.1f}",
        dst,
    )
