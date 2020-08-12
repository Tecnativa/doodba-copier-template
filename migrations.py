"""Template migration scripts.

This file is executed through invoke by copier when updating child projects.
"""
import re
import shutil
from pathlib import Path
from unittest import mock

from invoke import task
from invoke.util import yaml


def _load_yaml(yaml_path):
    """Load a yaml file."""
    with open(yaml_path) as yaml_fd:
        # HACK https://stackoverflow.com/a/44875714/1468388
        # TODO Remove hack when https://github.com/pyinvoke/invoke/issues/708 is fixed
        with mock.patch.object(
            yaml.reader.Reader,
            "NON_PRINTABLE",
            re.compile(
                "[^\x09\x0A\x0D\x20-\x7E\x85\xA0-"
                "\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]"
            ),
        ):
            return yaml.safe_load(yaml_fd)


@task
def from_doodba_scaffolding_to_copier(c):
    print("Removing remaining garbage from doodba-scaffolding.")
    shutil.rmtree(Path(".vscode", "doodba"), ignore_errors=True)
    garbage = (
        Path(".travis.yml"),
        Path(".vscode", "doodbasetup.py"),
        Path("odoo", "custom", "src", "private", ".empty"),
    )
    for path in garbage:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    # When using Copier >= 3.0.5, this file didn't get properly migrated
    editorconfig_file = Path(".editorconfig")
    editorconfig_contents = editorconfig_file.read_text()
    editorconfig_contents = editorconfig_contents.replace(
        "[*.yml]", "[*.{code-snippets,code-workspace,json,md,yaml,yml}{,.jinja}]", 1
    )
    editorconfig_file.write_text(editorconfig_contents)


@task
def remove_odoo_auto_folder(c):
    """This folder makes no more sense for us.

    The `invoke develop` task now handles its creation, which is done with
    host user UID and GID to avoid problems.

    There's no need to have it in our code tree anymore.
    """
    shutil.rmtree(Path("odoo", "auto"), ignore_errors=True)


@task
def update_domains_structure(c, dst_path, answers_rel_path):
    """Migrates from v1 to v2 domain structure.

    In template v1:

    - domain_prod was a str
    - domain_prod_alternatives was a list of str
    - domain_test was a str

    In template v2, we support multiple domains:

    - domains_prod is a dict {main: [redirected, ...], ...}
    - domains_staging is a list of str
    """
    answers_path = Path(dst_path, answers_rel_path)
    answers_yaml = _load_yaml(answers_path)
    answers_yaml.setdefault(
        "domains_prod",
        {
            answers_yaml.pop("domain_prod", None): answers_yaml.pop(
                "domain_prod_alternatives", []
            )
        },
    )
    domain_test = answers_yaml.pop("domain_test", None)
    answers_yaml.setdefault("domains_staging", [domain_test] if domain_test else [])
    answers_path.write_text(yaml.safe_dump(answers_yaml))
