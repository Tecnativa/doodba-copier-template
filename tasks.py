"""Template maintenance tasks.

These tasks are to be executed with https://www.pyinvoke.org/ in Python 3.8.1+
and are related to the maintenance of this template project, not the child
projects generated with it.
"""

from pathlib import Path

from invoke import task

TEMPLATE_ROOT = Path(__file__).parent.resolve()
ESSENTIALS = ("git", "python3", "uv")


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
        # Use uv to set up development environment in a local venv
        c.run("uv sync")
        c.run("uv run pre-commit install")


@task(develop)
def lint(c, verbose=False):
    """Lint & format source code."""
    flags = ["--show-diff-on-failure", "--all-files", "--color=always"]
    if verbose:
        flags.append("--verbose")
    flags = " ".join(flags)
    with c.cd(str(TEMPLATE_ROOT)):
        c.run(f"uv run pre-commit run {flags}")


@task(develop)
def test(c, verbose=False, sequential=False, docker=True):
    """Test project.

    Add --sequential to run only sequential tests, with parallelization disabled.
    """
    flags = ["--color=yes"]
    if verbose:
        flags.append("-vv")
    if not docker:
        flags.append("--skip-docker-tests")
    if sequential:
        flags.extend(["--dist", "no", "-m", "sequential"])
    else:
        flags.extend(["-m", '"not sequential"'])
    flags = " ".join(flags)
    cmd = f"uv run pytest {flags} tests"
    with c.cd(str(TEMPLATE_ROOT)):
        c.run(cmd)
