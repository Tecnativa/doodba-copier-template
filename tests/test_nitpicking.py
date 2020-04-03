"""Nitpicking small tests ahead."""
from pathlib import Path
from textwrap import dedent

import pytest
from copier.main import copy
from plumbum import local
from plumbum.cmd import diff, git

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
        git("commit", "--no-verify", "-am", "hello world")
        vscode = tmp_path / "odoo" / "custom" / "src" / "private" / ".vscode"
        vscode.mkdir()
        (vscode / "something").touch()
        assert not git("status", "--porcelain")


def test_mqt_configs_synced():
    """Make sure configs from MQT are in sync."""
    template = Path("tests", "default_settings", "v13.0")
    mqt = Path("vendor", "maintainer-quality-tools", "sample_files", "pre-commit-13.0")
    good_diffs = Path("tests", "good_diffs")
    for conf in (".pylintrc", ".pylintrc-mandatory"):
        good = (good_diffs / f"{conf}.diff").read_text()
        tested = diff(template / conf, mqt / conf, retcode=1)
        assert good == tested


def test_gitlab_badges(tmp_path: Path):
    """Gitlab badges are properly formatted in README."""
    copy(
        ".",
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"gitlab_url": "https://gitlab.example.com/Tecnativa/my-badged-odoo"},
    )
    expected_badges = dedent(
        """
        [![pipeline status](https://gitlab.example.com/Tecnativa/my-badged-odoo/badges/13.0/pipeline.svg)](https://gitlab.example.com/Tecnativa/my-badged-odoo/commits/13.0)
        [![coverage report](https://gitlab.example.com/Tecnativa/my-badged-odoo/badges/13.0/coverage.svg)](https://gitlab.example.com/Tecnativa/my-badged-odoo/commits/13.0)
        """
    )
    assert expected_badges.strip() in (tmp_path / "README.md").read_text()


def test_alt_domains_traefik2_rules(tmp_path: Path):
    """Make sure alt domains redirections are good for Traefik 2."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    clone_self_dirty(src)
    copy(
        str(src),
        str(dst),
        vcs_ref="HEAD",
        force=True,
        data={
            "domain_prod": "www.example.com",
            "domain_prod_alternatives": [
                "old.example.com",
                "example.com",
                "example.org",
                "www.example.org",
            ],
        },
    )
    expected = Path("tests", "samples", "alt-domains", "prod.yaml").read_text()
    generated = (dst / "prod.yaml").read_text()
    assert generated == expected


def test_template_update_badge(tmp_path: Path):
    """Test that the template update badge is properly formatted."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    tag = "v99999.0.0-99999-bye-bye"
    clone_self_dirty(src, tag=tag)
    copy(str(src), str(dst), vcs_ref=tag, force=True)
    expected = "[![Last template update](https://img.shields.io/badge/last%20template%20update-v99999.0.0--99999--bye--bye-informational)](https://github.com/Tecnativa/doodba-copier-template/tree/v99999.0.0-99999-bye-bye)"
    assert expected in (dst / "README.md").read_text()
