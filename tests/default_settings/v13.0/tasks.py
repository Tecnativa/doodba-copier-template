"""Doodba child project tasks.

This file is to be executed with https://www.pyinvoke.org/ in Python 3.6+.

Contains common helpers to develop using this child project.
"""
import json
import os
from glob import glob, iglob
from pathlib import Path

from invoke import task

SRC_PATH = Path("odoo", "custom", "src")
DEVELOP_DEPENDENCIES = (
    "copier",
    "docker-compose",
    "pre-commit",
)


@task
def write_code_workspace_file(c, cw_path=None):
    """Generate code-workspace file definition.

    Some other tasks will call this one when needed, and since you cannot specify
    the file name there, if you want a specific one, you should call this task
    before.

    Most times you just can forget about this task and let it be run automatically
    whenever needed.

    If you don't define a workspace name, this task will reuse the 1st
    `doodba.*.code-workspace` file found inside the current directory.
    If none is found, it will default to `doodba.$(basename $PWD).code-workspace`.

    If you define it manually, remember to use the same prefix and suffix if you
    want it git-ignored by default.
    Example: `--cw-path doodba.my-custom-name.code-workspace`
    """
    if not cw_path:
        try:
            cw_path = next(iglob(str(Path(c.cwd, "doodba.*.code-workspace"))))
        except StopIteration:
            cw_path = f"doodba.{Path(c.cwd).absolute().name}.code-workspace"
    try:
        with open(cw_path) as cw_fd:
            cw_config = json.load(cw_fd)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        cw_config = {}
    cw_config["folders"] = []
    addon_repos = glob(str(Path(c.cwd, SRC_PATH, "private")))
    addon_repos += glob(str(Path(c.cwd, SRC_PATH, "*", ".git", "..")))
    for subrepo in sorted(addon_repos):
        cw_config["folders"].append({"path": subrepo})
    # HACK https://github.com/microsoft/vscode/issues/37947 put top folder last
    cw_config["folders"].append({"path": "."})
    with open(cw_path, "w") as cw_fd:
        json.dump(cw_config, cw_fd, indent=2)
        cw_fd.write("\n")


@task
def develop(c):
    """Set up a basic development environment."""
    # Install basic dependencies
    for dep in DEVELOP_DEPENDENCIES:
        try:
            c.run(f"{dep} --version", hide=True)
        except Exception:
            try:
                c.run("pipx --version")
            except Exception:
                c.run("python3 -m pip install --user pipx")
            c.run(f"pipx install {dep}")
    # Prepare environment
    c.run("git init")
    c.run("ln -sf devel.yaml docker-compose.yml")
    write_code_workspace_file(c)
    c.run("pre-commit install")


@task(develop)
def git_aggregate(c):
    """Download odoo & addons git code.

    Executes git-aggregator from within the doodba container.
    """
    c.run(
        "docker-compose --file setup-devel.yaml run --rm odoo",
        env={"GID": str(os.getgid()), "UID": str(os.getuid()), "UMASK": "27"},
    )
    write_code_workspace_file(c)
    for git_folder in iglob(str(Path(c.cwd, SRC_PATH, "*", ".git", ".."))):
        action = (
            "install"
            if Path(git_folder, ".pre-commit-config.yaml").is_file()
            else "uninstall"
        )
        with c.cd(git_folder):
            c.run(f"pre-commit {action}")


@task(develop)
def img_build(c, pull=True):
    """Build docker images."""
    cmd = "docker-compose build"
    if pull:
        cmd += " --pull"
    c.run(cmd, env={"UID": str(os.getuid()), "GID": str(os.getgid())})


@task(develop)
def img_pull(c):
    """Pull docker images."""
    c.run("docker-compose pull")


@task(develop)
def lint(c, verbose=False):
    """Lint & format source code."""
    cmd = "pre-commit run --show-diff-on-failure --all-files --color=always"
    if verbose:
        cmd += " --verbose"
    c.run(cmd)


@task(develop)
def start(c, detach=True, ptvsd=False):
    """Start environment."""
    cmd = "docker-compose up"
    if detach:
        cmd += " --detach"
    c.run(cmd, env={"DOODBA_PTVSD_ENABLE": str(int(ptvsd))})


@task(develop, help={"purge": "Remove all related containers, images and volumes"})
def stop(c, purge=False):
    """Stop and (optionally) purge environment."""
    cmd = "docker-compose"
    if purge:
        cmd += " down --remove-orphans --rmi local --volumes"
    else:
        cmd += " stop"
    c.run(cmd)


@task(develop)
def restart(c, quick=True):
    """Restart odoo container(s)."""
    cmd = "docker-compose restart"
    if quick:
        cmd = f"{cmd} -t0"
    cmd = f"{cmd} odoo odoo_proxy"
    c.run(cmd)


@task(develop)
def logs(c, tail=10):
    """Obtain last logs of current environment."""
    cmd = "docker-compose logs -f"
    if tail:
        cmd += f" --tail {tail}"
    c.run(cmd)
