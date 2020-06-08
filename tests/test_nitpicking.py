"""Nitpicking small tests ahead."""
import json
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from copier.main import copy
from plumbum import local
from plumbum.cmd import diff, git, invoke, pre_commit

WHITESPACE_PREFIXED_LICENSES = (
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "LGPL-3.0-or-later",
)


@pytest.mark.parametrize("project_license", WHITESPACE_PREFIXED_LICENSES)
def test_license_whitespace_prefix(
    tmp_path: Path, cloned_template: Path, project_license
):
    dst = tmp_path / "dst"
    copy(
        str(cloned_template),
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


def test_mqt_configs_synced(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
):
    """Make sure configs from MQT are in sync."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="test",
        force=True,
        data={"odoo_version": supported_odoo_version},
    )
    mqt = Path("vendor", "maintainer-quality-tools", "sample_files", "pre-commit-13.0")
    good_diffs = Path("tests", "samples", "mqt-diffs")
    for conf in (".pylintrc", ".pylintrc-mandatory"):
        good = (good_diffs / f"{conf}.diff").read_text()
        tested = diff(tmp_path / conf, mqt / conf, retcode=1)
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


def test_alt_domains_rules(tmp_path: Path, cloned_template: Path):
    """Make sure alt domains redirections are good for Traefik."""
    copy(
        str(cloned_template),
        str(tmp_path),
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
    with local.cwd(tmp_path):
        git("add", "prod.yaml")
        pre_commit("run", "-a", retcode=1)
    expected = Path("tests", "samples", "alt-domains", "prod.yaml").read_text()
    generated = (tmp_path / "prod.yaml").read_text()
    generated_scalar = yaml.safe_load(generated)
    # Any of these characters in a traefik label is an error almost for sure
    error_chars = ("\n", "'", '"')
    for service in generated_scalar["services"].values():
        for key, value in service.get("labels", {}).items():
            if not key.startswith("traefik."):
                continue
            for char in error_chars:
                assert char not in key
                assert char not in str(value)
    assert generated == expected


def test_cidr_whitelist_rules(tmp_path: Path, cloned_template: Path):
    """Make sure CIDR whitelist redirections are good for Traefik."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"cidr_whitelist": ["123.123.123.123/24", "456.456.456.456"]},
    )
    with local.cwd(tmp_path):
        git("add", "prod.yaml", "test.yaml")
        pre_commit("run", "-a", retcode=1)
    expected = Path("tests", "samples", "cidr-whitelist")
    assert (tmp_path / "prod.yaml").read_text() == (expected / "prod.yaml").read_text()
    assert (tmp_path / "test.yaml").read_text() == (expected / "test.yaml").read_text()


def test_code_workspace_file(tmp_path: Path, cloned_template: Path):
    """The file is generated as expected."""
    copy(
        str(cloned_template), str(tmp_path), vcs_ref="HEAD", force=True,
    )
    assert (tmp_path / f"doodba.{tmp_path.name}.code-workspace").is_file()
    (tmp_path / f"doodba.{tmp_path.name}.code-workspace").rename(
        tmp_path / "doodba.other1.code-workspace"
    )
    with local.cwd(tmp_path):
        invoke("write-code-workspace-file")
        assert (tmp_path / "doodba.other1.code-workspace").is_file()
        assert not (tmp_path / f"doodba.{tmp_path.name}.code-workspace").is_file()
        # Do a stupid and dirty git clone to check it's sorted fine
        git("clone", cloned_template, Path("odoo", "custom", "src", "zzz"))
        invoke("write-code-workspace-file", "-c", "doodba.other2.code-workspace")
        assert not (tmp_path / f"doodba.{tmp_path.name}.code-workspace").is_file()
        assert (tmp_path / "doodba.other1.code-workspace").is_file()
        assert (tmp_path / "doodba.other2.code-workspace").is_file()
        with (tmp_path / "doodba.other2.code-workspace").open() as fp:
            workspace_definition = json.load(fp)
        assert workspace_definition == {
            "folders": [
                {"path": "odoo/custom/src/zzz"},
                {"path": "odoo/custom/src/private"},
                {"path": "."},
            ]
        }


def test_dotdocker_ignore_content(tmp_path: Path, cloned_template: Path):
    """Everything inside .docker must be ignored."""
    copy(
        str(cloned_template), str(tmp_path), vcs_ref="HEAD", force=True,
    )
    with local.cwd(tmp_path):
        git("add", ".")
        git("commit", "-am", "hello", retcode=1)
        git("commit", "-am", "hello")
        (tmp_path / ".docker" / "some-file").touch()
        assert not git("status", "--porcelain")


def test_template_update_badge(tmp_path: Path, cloned_template: Path):
    """Test that the template update badge is properly formatted."""
    tag = "v99999.0.0-99999-bye-bye"
    with local.cwd(cloned_template):
        git("tag", "--delete", "test")
        git("tag", "--force", tag)
    copy(str(cloned_template), str(tmp_path), vcs_ref=tag, force=True)
    expected = "[![Last template update](https://img.shields.io/badge/last%20template%20update-v99999.0.0--99999--bye--bye-informational)](https://github.com/Tecnativa/doodba-copier-template/tree/v99999.0.0-99999-bye-bye)"
    assert expected in (tmp_path / "README.md").read_text()


def test_pre_commit_config(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
):
    """Test that .pre-commit-config.yaml has some specific settings fine."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"odoo_version": supported_odoo_version},
    )
    pre_commit_config = yaml.safe_load(
        (tmp_path / ".pre-commit-config.yaml").read_text()
    )
    is_py3 = supported_odoo_version >= 11
    found = 0
    should_find = 1
    for repo in pre_commit_config["repos"]:
        if repo["repo"] == "https://github.com/pre-commit/pre-commit-hooks":
            found += 1
            if is_py3:
                assert {"id": "debug-statements"} in repo["hooks"]
                assert {"id": "fix-encoding-pragma", "args": ["--remove"]} in repo[
                    "hooks"
                ]
            else:
                assert {"id": "debug-statements"} not in repo["hooks"]
                assert {"id": "fix-encoding-pragma", "args": ["--remove"]} not in repo[
                    "hooks"
                ]
                assert {"id": "fix-encoding-pragma"} in repo["hooks"]
    assert found == should_find


def test_no_python_write_bytecode_in_devel(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
):
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"odoo_version": supported_odoo_version},
    )
    devel = yaml.safe_load((tmp_path / "devel.yaml").read_text())
    assert devel["services"]["odoo"]["environment"]["PYTHONDONTWRITEBYTECODE"] == 1
