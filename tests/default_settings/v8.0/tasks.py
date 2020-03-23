# -*- coding: utf-8 -*-
"""Doodba child project tasks.

This file is to be executed with https://www.pyinvoke.org/ in Python 3.6+.

Contains common helpers to develop using this child project.
"""
import json
import os
import re
from glob import glob, iglob
from pathlib import Path
from unittest.mock import patch

from invoke import task
from invoke.util import yaml
from invoke.vendor.yaml3.reader import Reader

SRC_PATH = Path("odoo", "custom", "src")
DEVELOP_DEPENDENCIES = (
    "copier",
    "docker-compose",
    "pre-commit",
)


def _load_answers():
    """Load copier answers file. This must be run after develop."""
    with open(".copier-answers.yml", "r") as answers_fd:
        # HACK https://github.com/pyinvoke/invoke/issues/708
        with patch.object(
            Reader,
            "NON_PRINTABLE",
            re.compile(
                "[^\x09\x0A\x0D\x20-\x7E\x85\xA0-"
                "\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]"
            ),
        ):
            return yaml.safe_load(answers_fd)


def _write_code_workspace_file():
    """Generate code-workspace file definition"""
    answers = _load_answers()
    cw_path = f"doodba.{answers['project_name']}.code-workspace"
    try:
        with open(cw_path) as cw_fd:
            cw_config = json.load(cw_fd)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        cw_config = {}
    cw_config["folders"] = []
    addon_repos = glob(str(SRC_PATH / "private"))
    addon_repos += glob(str(SRC_PATH / "*" / ".git" / ".."))
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
    _write_code_workspace_file()
    c.run("pre-commit install")


@task(develop)
def git_aggregate(c):
    """Download odoo & addons git code.

    Executes git-aggregator from within the doodba container.
    """
    c.run(
        "docker-compose --file setup-devel.yaml run --rm odoo",
        env={"GID": os.getgid(), "UID": os.getuid(), "UMASK": 27},
    )
    _write_code_workspace_file()
    for pre_commit_folder in iglob(
        str(SRC_PATH / "*" / ".git" / ".." / ".pre-commit-config.yaml" / ".")
    ):
        with c.cd(pre_commit_folder):
            c.run("pre-commit install")


@task(develop)
def img_build(c, pull=True):
    """Build docker images."""
    cmd = "docker-compose build"
    if pull:
        cmd += " --pull"
    c.run(cmd, env={"UID": os.getuid(), "GID": os.getgid()})


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
    c.run(cmd, env={"DOODBA_PTVSD_ENABLE": int(ptvsd)})


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
