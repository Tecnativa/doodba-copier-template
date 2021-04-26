"""Nitpicking small tests ahead."""
import json
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from copier.main import copy
from plumbum import ProcessExecutionError, local
from plumbum.cmd import diff, docker_compose, git, invoke, pre_commit

from .conftest import LAST_ODOO_VERSION, build_file_tree, generate_test_addon

WHITESPACE_PREFIXED_LICENSES = (
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "LGPL-3.0-or-later",
)


def test_doodba_main_domain_label(cloned_template: Path, tmp_path: Path):
    """Make sure the doodba.domain.main label is correct."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="test",
        force=True,
        data={
            "domains_prod": [
                {
                    "hosts": ["not0.prod.example.com", "not1.prod.example.com"],
                    "redirect_to": "yes.prod.example.com",
                },
                {
                    "hosts": ["not3.prod.example.com", "not4.prod.example.com"],
                    "path_prefixes": ["/insecure/"],
                    "entrypoints": ["web-insecure"],
                },
                {"hosts": ["yes.prod.example.com", "not5.prod.example.com"]},
            ],
            "domains_test": [
                {
                    "hosts": ["not0.test.example.com", "not1.test.example.com"],
                    "redirect_to": "yes.test.example.com",
                },
                {
                    "hosts": ["not3.test.example.com", "not4.test.example.com"],
                    "path_prefixes": ["/insecure/"],
                    "entrypoints": ["web-insecure"],
                },
                {"hosts": ["yes.test.example.com", "not5.test.example.com"]},
            ],
        },
    )
    with local.cwd(tmp_path):
        prod_config = yaml.load(docker_compose("-f", "prod.yaml", "config"))
        test_config = yaml.load(docker_compose("-f", "test.yaml", "config"))
        assert (
            prod_config["services"]["odoo"]["labels"]["doodba.domain.main"]
            == "yes.prod.example.com"
        )
        assert (
            test_config["services"]["odoo"]["labels"]["doodba.domain.main"]
            == "yes.test.example.com"
        )
        # These labels must be present to avoid that Traefik 1 builds its own
        # main domain assumption and tries to download its Let's Encrypt certs,
        # which would possibly fail and hit LE's rate limits
        # TODO Remove asserts when dropping Traefik 1 support
        assert (
            prod_config["services"]["odoo"]["labels"]["traefik.domain"]
            == "yes.prod.example.com"
        )
        assert (
            test_config["services"]["odoo"]["labels"]["traefik.domain"]
            == "yes.test.example.com"
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


def test_no_vscode_in_private(cloned_template: Path, tmp_path: Path):
    """Make sure .vscode folders are git-ignored in private folder."""
    copy(str(cloned_template), str(tmp_path), vcs_ref="HEAD", force=True)
    with local.cwd(tmp_path):
        git("add", ".")
        git("commit", "--no-verify", "-am", "hello world")
        vscode = tmp_path / "odoo" / "custom" / "src" / "private" / ".vscode"
        vscode.mkdir()
        (vscode / "something").touch()
        assert not git("status", "--porcelain")


def test_mqt_configs_synced(
    tmp_path: Path, cloned_template: Path, any_odoo_version: float
):
    """Make sure configs from MQT are in sync."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="test",
        force=True,
        data={"odoo_version": any_odoo_version},
    )
    tmp_oca_path = tmp_path / ".." / "oca-addons-repo-files"
    tmp_oca_path.mkdir()
    copy(
        str(Path("vendor", "oca-addons-repo-template")),
        tmp_oca_path,
        vcs_ref="HEAD",
        force=True,
        data={"odoo_version": any_odoo_version if any_odoo_version >= 13 else "13.0"},
        exclude=["**", "!.pylintrc*"],
    )
    good_diffs = Path("tests", "samples", "mqt-diffs")
    for conf in (".pylintrc", ".pylintrc-mandatory"):
        good = (good_diffs / f"v{any_odoo_version}-{conf}.diff").read_text()
        tested = diff(tmp_path / conf, tmp_oca_path / conf, retcode=1)
        assert good == tested


def test_pre_commit_in_template():
    """Make sure linters are happy."""
    with local.cwd(Path(__file__).parent.parent):
        invoke("lint")


def test_gitlab_badges(cloned_template: Path, tmp_path: Path):
    """Gitlab badges are properly formatted in README."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"gitlab_url": "https://gitlab.example.com/Tecnativa/my-badged-odoo"},
    )
    expected_badges = dedent(
        f"""
        [![pipeline status](https://gitlab.example.com/Tecnativa/my-badged-odoo/badges/{LAST_ODOO_VERSION}/pipeline.svg)](https://gitlab.example.com/Tecnativa/my-badged-odoo/commits/{LAST_ODOO_VERSION})
        [![coverage report](https://gitlab.example.com/Tecnativa/my-badged-odoo/badges/{LAST_ODOO_VERSION}/coverage.svg)](https://gitlab.example.com/Tecnativa/my-badged-odoo/commits/{LAST_ODOO_VERSION})
        """
    )
    assert expected_badges.strip() in (tmp_path / "README.md").read_text()


def test_cidr_whitelist_rules(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
):
    """Make sure CIDR whitelist redirections are good for Traefik."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={
            "odoo_version": supported_odoo_version,
            "project_name": "test-cidr-whitelist",
            "cidr_whitelist": ["123.123.123.123/24", "456.456.456.456"],
            "domains_prod": [{"hosts": ["www.example.com"]}],
            "domains_test": [{"hosts": ["demo.example.com"]}],
        },
    )
    # TODO Use Traefik to test this, instead of asserting labels
    key = ("test-cidr-whitelist-%.1f" % supported_odoo_version).replace(".", "-")
    with local.cwd(tmp_path):
        git("add", "prod.yaml", "test.yaml")
        pre_commit("run", "-a", retcode=None)
        prod = yaml.safe_load(docker_compose("-f", "prod.yaml", "config"))
        test = yaml.safe_load(docker_compose("-f", "test.yaml", "config"))
    # Assert prod.yaml
    assert (
        prod["services"]["odoo"]["labels"][
            f"traefik.http.middlewares.{key}-prod-whitelist.IPWhiteList.sourceRange"
        ]
        == "123.123.123.123/24, 456.456.456.456"
    )
    assert f"{key}-prod-whitelist" in prod["services"]["odoo"]["labels"][
        f"traefik.http.routers.{key}-prod-main-0.middlewares"
    ].split(", ")
    assert f"{key}-prod-whitelist" in prod["services"]["odoo"]["labels"][
        f"traefik.http.routers.{key}-prod-longpolling-0.middlewares"
    ].split(", ")
    assert f"{key}-prod-whitelist" in prod["services"]["odoo"]["labels"][
        f"traefik.http.routers.{key}-prod-forbiddenCrawlers-0.middlewares"
    ].split(", ")
    # Assert test.yaml
    assert (
        test["services"]["smtp"]["labels"][
            f"traefik.http.middlewares.{key}-test-whitelist.IPWhiteList.sourceRange"
        ]
        == "123.123.123.123/24, 456.456.456.456"
    )
    assert f"{key}-test-whitelist" in test["services"]["odoo"]["labels"][
        f"traefik.http.routers.{key}-test-forbiddenCrawlers-0.middlewares"
    ].split(", ")
    assert f"{key}-test-whitelist" in test["services"]["odoo"]["labels"][
        f"traefik.http.routers.{key}-test-longpolling-0.middlewares"
    ].split(", ")
    assert f"{key}-test-whitelist" in test["services"]["smtp"]["labels"][
        f"traefik.http.routers.{key}-test-mailhog-0.middlewares"
    ].split(", ")


def test_code_workspace_file(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
):
    """The file is generated as expected."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
        data={"odoo_version": supported_odoo_version},
    )
    assert (tmp_path / f"doodba.{tmp_path.name}.code-workspace").is_file()
    (tmp_path / f"doodba.{tmp_path.name}.code-workspace").rename(
        tmp_path / "doodba.other1.code-workspace"
    )
    with local.cwd(tmp_path / "odoo" / "custom" / "src" / "private"):
        # Generate generic addon path
        is_py3 = supported_odoo_version >= 11
        manifest = "__manifest__" if is_py3 else "__openerp__"
        build_file_tree(
            {
                f"test_module_static/{manifest}.py": f"""\
                    {"{"}
                    'name':'test module','license':'AGPL-3',
                    'version':'{supported_odoo_version}.1.0.0',
                    'installable': True,
                    'auto_install': False
                    {"}"}
                """,
                "test_module_static/static/index.html": """\
                    <html>
                    </html>
                """,
            }
        )
    with local.cwd(tmp_path):
        invoke("write-code-workspace-file")
        assert (tmp_path / "doodba.other1.code-workspace").is_file()
        assert not (tmp_path / f"doodba.{tmp_path.name}.code-workspace").is_file()
        # Do a stupid and dirty git clone to check it's sorted fine
        git("clone", cloned_template, Path("odoo", "custom", "src", "zzz"))
        # "Clone" a couple more repos, including odoo to check order
        git("clone", cloned_template, Path("odoo", "custom", "src", "aaa"))
        git("clone", cloned_template, Path("odoo", "custom", "src", "bbb"))
        git("clone", cloned_template, Path("odoo", "custom", "src", "odoo"))
        invoke("write-code-workspace-file", "-c", "doodba.other2.code-workspace")
        assert not (tmp_path / f"doodba.{tmp_path.name}.code-workspace").is_file()
        assert (tmp_path / "doodba.other1.code-workspace").is_file()
        assert (tmp_path / "doodba.other2.code-workspace").is_file()
        with (tmp_path / "doodba.other2.code-workspace").open() as fp:
            workspace_definition = json.load(fp)
        # Check workspace folder definition and order
        assert workspace_definition["folders"] == [
            {"path": "odoo/custom/src/aaa"},
            {"path": "odoo/custom/src/bbb"},
            {"path": "odoo/custom/src/zzz"},
            {"path": "odoo/custom/src/odoo"},
            {"path": "odoo/custom/src/private"},
            {"name": f"doodba.{tmp_path.name}", "path": "."},
        ]
        # Firefox debugger configuration
        url = f"http://localhost:{supported_odoo_version:.0f}069/test_module_static/static/"
        path = "${workspaceFolder:private}/test_module_static/static/"
        firefox_configuration = next(
            conf
            for conf in workspace_definition["launch"]["configurations"]
            if conf["type"] == "firefox"
        )
        assert {"url": url, "path": path} in firefox_configuration["pathMappings"]
        # Chrome debugger configuration
        chrome_configuration = next(
            conf
            for conf in workspace_definition["launch"]["configurations"]
            if conf["type"] == "chrome"
        )
        assert chrome_configuration["pathMapping"][url] == path


def test_dotdocker_ignore_content(tmp_path: Path, cloned_template: Path):
    """Everything inside .docker must be ignored."""
    copy(
        str(cloned_template),
        str(tmp_path),
        vcs_ref="HEAD",
        force=True,
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
        git("commit", "--allow-empty", "-m", "dumb commit")
        git("tag", "--force", tag)
    copy(str(cloned_template), str(tmp_path), vcs_ref=tag, force=True)
    expected = "[![Last template update](https://img.shields.io/badge/last%20template%20update-v99999.0.0--99999--bye--bye-informational)](https://github.com/Tecnativa/doodba-copier-template/tree/v99999.0.0-99999-bye-bye)"
    assert expected in (tmp_path / "README.md").read_text()


def test_pre_commit_in_subproject(
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
    # Make sure the template was correctly rendered
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
    # Make sure it reformats correctly some files
    with local.cwd(tmp_path / "odoo" / "custom" / "src" / "private"):
        git("add", "-A")
        git("commit", "-m", "hello world", retcode=1)
        git("commit", "-am", "hello world")
        manifest = "__manifest__" if is_py3 else "__openerp__"
        generate_test_addon("test_module", supported_odoo_version, ugly=True)
        git("add", "-A")
        git("commit", "-m", "added test_module", retcode=1)
        git("commit", "-am", "added test_module")
        expected_samples = {
            f"test_module/{manifest}.py": f"""\
                {"{"}
                    "name": "test_module",
                    "license": "AGPL-3",
                    "version": "{supported_odoo_version}.1.0.0",
                    "depends": ["base"],
                    "installable": True,
                    "auto_install": False,
                {"}"}
            """,
            "test_module/__init__.py": """\
                from . import models
            """,
            "test_module/models/__init__.py": """\
                from . import res_partner
            """,
            "test_module/models/res_partner.py": '''\
                import io
                import sys
                from logging import getLogger
                from os.path import join

                from requests import get

                import odoo
                from odoo import models

                _logger = getLogger(__name__)


                class ResPartner(models.Model):
                    _inherit = "res.partner"

                    def some_method(self, test):
                        """some weird
                        docstring"""
                        _logger.info(models, join, get, io, sys, odoo)
            ''',
        }
        for path, content in expected_samples.items():
            content = dedent(content)
            if not is_py3 and path.endswith(".py"):
                content = f"# -*- coding: utf-8 -*-\n{content}"
            assert Path(path).read_text() == content
    # Make sure it doesn't fail for incorrect module version when addon not installable
    with local.cwd(tmp_path / "odoo" / "custom" / "src" / "private"):
        # Bump version in test module and set as not installable
        generate_test_addon(
            "test_module", supported_odoo_version + 1, installable=False
        )
        git("add", "-A")
        # First commit will add new module to the exclude list in pre-commit
        git("commit", "-m", "start migration of test_module", retcode=1)
        # Module should now be ignored by pre-commit and give no problems in commit
        git("commit", "-am", "start migration of test_module")
        # Load pre-commit config
        with open(tmp_path / ".pre-commit-config.yaml", "r") as fd:
            pre_commit_config = yaml.safe_load(fd.read())
        assert "^odoo/custom/src/private/test_module/|" in pre_commit_config["exclude"]
        # Make sure uninstallable addon was ignored by pre-commit
        pre_commit("run", "-a")
        assert "test_module" not in git("status", "--porcelain")
    # It should still fail for installable addon with bad manifest
    with local.cwd(tmp_path / "odoo" / "custom" / "src" / "private"):
        # Mark test module as installable again
        generate_test_addon("test_module", supported_odoo_version + 1, installable=True)
        git("add", "-A")
        # First commit will remove test module to the exclude list in pre-commit
        git("commit", "-m", "Mark test module as installable again", retcode=1)
        # Commit should fail for incorrect version
        with pytest.raises(ProcessExecutionError):
            git("commit", "-am", "Mark test_module as installable again")
        # Load pre-commit config
        with open(tmp_path / ".pre-commit-config.yaml", "r") as fd:
            pre_commit_config = yaml.safe_load(fd.read())
        assert (
            "^odoo/custom/src/private/test_module/|" not in pre_commit_config["exclude"]
        )


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
