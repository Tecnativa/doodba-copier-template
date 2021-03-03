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
def remove_vscode_launch_and_tasks(c, dst_path):
    """Remove .vscode/{launch,tasks}.json file.

    Launch configurations are now generated in the doodba.*.code-workspace file.
    """
    for fname in ("launch", "tasks"):
        garbage = Path(dst_path, ".vscode", f"{fname}.json")
        if garbage.is_file():
            garbage.unlink()


@task
def remove_vscode_settings(c, dst_path):
    """Remove .vscode/{launch,tasks}.json file.

    Launch configurations are now generated in the doodba.*.code-workspace file.
    """
    garbage = Path(dst_path, ".vscode", "settings.json")
    if garbage.is_file():
        garbage.unlink()


@task
def update_domains_structure(c, dst_path, answers_rel_path):
    """Migrates from v1 to v2 domain structure.

    In template v1:

    - domain_prod was a str
    - domain_prod_alternatives was a list of str
    - domain_test was a str

    In template v2, we support multiple domains:

    - domains_prod is a list of dicts
    - domains_test is a list of dicts
    """
    answers_path = Path(dst_path, answers_rel_path)
    answers_yaml = _load_yaml(answers_path)
    # Update domains_prod
    domain_prod = answers_yaml.pop("domain_prod", None)
    domain_prod_alternatives = answers_yaml.pop("domain_prod_alternatives", None)
    new_domains_prod = []
    if domain_prod:
        new_domains_prod.append(
            {"hosts": [domain_prod], "cert_resolver": "letsencrypt"}
        )
        if domain_prod_alternatives:
            new_domains_prod.append(
                {
                    "hosts": domain_prod_alternatives,
                    "cert_resolver": "letsencrypt",
                    "redirect_to": domain_prod,
                }
            )
    answers_yaml.setdefault("domains_prod", new_domains_prod)
    # Update domains_test
    domain_test = answers_yaml.pop("domain_test", None)
    new_domains_test = []
    if domain_test:
        new_domains_test.append(
            {"hosts": [domain_test], "cert_resolver": "letsencrypt"}
        )
    answers_yaml.setdefault("domains_test", new_domains_test)
    answers_path.write_text(yaml.safe_dump(answers_yaml))
    # Remove .env file
    Path(dst_path, ".env").unlink()
