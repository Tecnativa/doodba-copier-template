"""Template maintenance tasks.

These tasks are to be executed with https://www.pyinvoke.org/ in Python 3.6+
and are related to the maintenance of this template project, not the child
projects generated with it.
"""
import re
import tempfile
from pathlib import Path
from unittest import mock

from invoke import task
from invoke.util import yaml

TEMPLATE_ROOT = Path(__file__).parent.resolve()
ESSENTIALS = ("git", "python3", "poetry")


def _load_copier_conf():
    """Load copier.yml."""
    with open("copier.yml") as copier_fd:
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
            return yaml.safe_load(copier_fd)


@task
def check_dependencies(c):
    """Check essential development dependencies are present."""
    failures = []
    for dependency in ESSENTIALS:
        try:
            c.run(f"{dependency} --version", hide=True)
        except Exception:
            failures.append(dependency)
    if failures:
        print(f"Missing essential dependencies: {failures}")


@task(check_dependencies)
def develop(c):
    """Set up a development environment."""
    with c.cd(str(TEMPLATE_ROOT)):
        c.run("git submodule update --init --checkout --recursive")
        # Use poetry to set up development environment in a local venv
        c.run("poetry install")
        c.run("poetry run pre-commit install")


@task(develop)
def lint(c, verbose=False):
    """Lint & format source code."""
    flags = ["--show-diff-on-failure", "--all-files", "--color=always"]
    if verbose:
        flags.append("--verbose")
    flags = " ".join(flags)
    with c.cd(str(TEMPLATE_ROOT)):
        c.run(f"poetry run pre-commit run {flags}")


@task(develop)
def test(c, verbose=False):
    """Test project."""
    flags = ["-n", "auto", "--color=yes"]
    if verbose:
        flags.append("-vv")
    flags = " ".join(flags)
    with c.cd(str(TEMPLATE_ROOT)):
        c.run(f"poetry run pytest {flags} tests")


@task(develop)
def update_test_samples(c):
    """Update test samples renderings.

    Since this project is just a template, some render results are stored as
    tests to be able to check the templates produce the right results.

    However, when something changes, the samples must be properly updated and
    reviewed to make sure they are still OK.

    This job updates all those samples.
    """
    with c.cd(str(TEMPLATE_ROOT)):
        # Make sure git repo is clean
        try:
            c.run("git diff --quiet --exit-code")
        except Exception:
            print("git repo is dirty; clean it and repeat")
            raise
        copier_conf = _load_copier_conf()
        default_odoo_version = copier_conf["odoo_version"]["default"]
        samples = Path("tests", "samples")
        for file_name in (".pylintrc", ".pylintrc-mandatory"):
            with (samples / "mqt-diffs" / f"{file_name}.diff").open(
                "w"
            ) as fd, tempfile.mkdtemp(prefix="dct-samples") as copy_path:
                c.run(
                    "poetry run copier -fr HEAD -x '**' -x '!.pylintrc*' "
                    f"copy . {copy_path}"
                )
                own = Path(copy_path, f"v{default_odoo_version}", file_name)
                mqt = Path(
                    "vendor",
                    "maintainer-quality-tools",
                    "sample_files",
                    f"pre-commit-{default_odoo_version}",
                    file_name,
                )
                fd.write(c.run(f"diff {own} {mqt}", warn=True).stdout)
        c.run(
            "poetry run copier -fr HEAD -x '**' -x '!prod.yaml' "
            "-d domains_prod='{www.example.com: [old.example.com, example.com, example.org, www.example.org]' "
            f"copy . {samples / 'alt-domains'}",
            warn=True,
        )
        c.run("poetry run pre-commit run -a", warn=True)
