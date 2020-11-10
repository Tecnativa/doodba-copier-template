"""Doodba child project tasks.

This file is to be executed with https://www.pyinvoke.org/ in Python 3.6+.

Contains common helpers to develop using this child project.
"""
import json
import os
import tempfile
import time
from itertools import chain
from logging import getLogger
from pathlib import Path
from shutil import which

from invoke import exceptions, task
from invoke.util import yaml

PROJECT_ROOT = Path(__file__).parent.absolute()
SRC_PATH = PROJECT_ROOT / "odoo" / "custom" / "src"
UID_ENV = {"GID": str(os.getgid()), "UID": str(os.getuid()), "UMASK": "27"}
SERVICES_WAIT_TIME = int(os.environ.get("SERVICES_WAIT_TIME", 4))
ODOO_VERSION = float(
    yaml.safe_load((PROJECT_ROOT / "common.yaml").read_text())["services"]["odoo"][
        "build"
    ]["args"]["ODOO_VERSION"]
)

_logger = getLogger(__name__)


def _override_docker_command(service, command, file, orig_file=None):
    # Read config from main file
    if orig_file:
        with open(orig_file, "r") as fd:
            orig_docker_config = yaml.safe_load(fd.read())
            docker_compose_file_version = orig_docker_config.get("version")
    else:
        docker_compose_file_version = "2.4"
    docker_config = {
        "version": docker_compose_file_version,
        "services": {service: {"command": command}},
    }
    docker_config_yaml = yaml.dump(docker_config)
    file.write(docker_config_yaml)
    file.flush()


def _remove_auto_reload(file, orig_file):
    with open(orig_file, "r") as fd:
        orig_docker_config = yaml.safe_load(fd.read())
    odoo_command = orig_docker_config["services"]["odoo"]["command"]
    new_odoo_command = []
    for flag in odoo_command:
        if flag.startswith("--dev"):
            flag = flag.replace("reload,", "")
        new_odoo_command.append(flag)
    _override_docker_command("odoo", new_odoo_command, file, orig_file=orig_file)


def _get_cwd_addon(file):
    cwd = Path(file)
    manifest_file = False
    while PROJECT_ROOT < cwd:
        manifest_file = (cwd / "__manifest__.py").exists() or (
            cwd / "__openerp__.py"
        ).exists()
        if manifest_file:
            return cwd.stem
        cwd = cwd.parent
        if cwd == PROJECT_ROOT:
            return None


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
    root_name = f"doodba.{PROJECT_ROOT.name}"
    root_var = "${workspaceRoot:%s}" % root_name
    if not cw_path:
        try:
            cw_path = next(PROJECT_ROOT.glob("doodba.*.code-workspace"))
        except StopIteration:
            cw_path = f"{root_name}.code-workspace"
    if not Path(cw_path).is_absolute():
        cw_path = PROJECT_ROOT / cw_path
    cw_config = {}
    try:
        with open(cw_path) as cw_fd:
            cw_config = json.load(cw_fd)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        pass  # Nevermind, we start with a new config
    # Launch configurations
    debugpy_configuration = {
        "name": "Attach Python debugger to running container",
        "type": "python",
        "request": "attach",
        "pathMappings": [{"localRoot": f"{root_var}/odoo", "remoteRoot": "/opt/odoo"}],
        "port": int(ODOO_VERSION) * 1000 + 899,
        "host": "localhost",
    }
    firefox_configuration = {
        "type": "firefox",
        "request": "launch",
        "reAttach": True,
        "name": "Connect to firefox debugger",
        "url": f"http://localhost:{ODOO_VERSION:.0f}069/?debug=assets",
        "reloadOnChange": {
            "watch": f"{root_var}/odoo/custom/src/**/*.{'{js,css,scss,less}'}"
        },
        "skipFiles": ["**/lib/**"],
        "pathMappings": [],
    }
    chrome_executable = which("chrome") or which("chromium")
    chrome_configuration = {
        "type": "chrome",
        "request": "launch",
        "name": "Connect to chrome debugger",
        "url": f"http://localhost:{ODOO_VERSION:.0f}069/?debug=assets",
        "skipFiles": ["**/lib/**"],
        "trace": True,
        "pathMapping": {},
    }
    if chrome_executable:
        chrome_configuration["runtimeExecutable"] = chrome_executable
    cw_config["launch"] = {
        "compounds": [
            {
                "name": "Start Odoo and debug Python",
                "configurations": ["Attach Python debugger to running container"],
                "preLaunchTask": "Start Odoo in debug mode",
            },
            {
                "name": "Run and debug Odoo tests",
                "configurations": ["Attach Python debugger to running container"],
                "preLaunchTask": "Run Odoo Tests in debug mode for current module",
                "internalConsoleOptions": "openOnSessionStart",
            },
            {
                "name": "Start Odoo and debug JS in Firefox",
                "configurations": ["Connect to firefox debugger"],
                "preLaunchTask": "Start Odoo",
            },
            {
                "name": "Start Odoo and debug JS in Chrome",
                "configurations": ["Connect to chrome debugger"],
                "preLaunchTask": "Start Odoo",
            },
            {
                "name": "Start Odoo and debug Python + JS in Firefox",
                "configurations": [
                    "Attach Python debugger to running container",
                    "Connect to firefox debugger",
                ],
                "preLaunchTask": "Start Odoo in debug mode",
            },
            {
                "name": "Start Odoo and debug Python + JS in Chrome",
                "configurations": [
                    "Attach Python debugger to running container",
                    "Connect to chrome debugger",
                ],
                "preLaunchTask": "Start Odoo in debug mode",
            },
        ],
        "configurations": [
            debugpy_configuration,
            firefox_configuration,
            chrome_configuration,
        ],
    }
    # Configure folders
    cw_config["folders"] = []
    for subrepo in SRC_PATH.glob("*"):
        if not subrepo.is_dir():
            continue
        if (subrepo / ".git").exists() and subrepo.name != "odoo":
            cw_config["folders"].append(
                {"path": str(subrepo.relative_to(PROJECT_ROOT))}
            )
        debugpy_configuration["pathMappings"].append(
            {
                "localRoot": "${workspaceRoot:%s}" % subrepo.name,
                "remoteRoot": f"/opt/odoo/custom/src/{subrepo.name}",
            }
        )
        for addon in chain(subrepo.glob("*"), subrepo.glob("addons/*")):
            if (addon / "__manifest__.py").is_file() or (
                addon / "__openerp__.py"
            ).is_file():
                url = f"http://localhost:{ODOO_VERSION:.0f}069/{addon.name}/static/"
                path = "${workspaceRoot:%s}/%s/static/" % (
                    subrepo.name,
                    addon.relative_to(subrepo),
                )
                firefox_configuration["pathMappings"].append({"url": url, "path": path})
                chrome_configuration["pathMapping"][url] = path
    cw_config["tasks"] = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "Start Odoo",
                "type": "process",
                "command": "invoke",
                "args": ["start", "--detach"],
                "presentation": {
                    "echo": True,
                    "reveal": "silent",
                    "focus": False,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {"statusbar": {"label": "$(play-circle)"}},
            },
            {
                "label": "Run Odoo Tests for current module",
                "type": "process",
                "command": "invoke",
                "args": ["test", "--cur-file", "${file}"],
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": True,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {"statusbar": {"hide": True}},
            },
            {
                "label": "Run Odoo Tests in debug mode for current module",
                "type": "process",
                "command": "invoke",
                "args": [
                    "test",
                    "--cur-file",
                    "${file}",
                    "--debugpy",
                ],
                "presentation": {
                    "echo": True,
                    "reveal": "silent",
                    "focus": False,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {"statusbar": {"hide": True}},
            },
            {
                "label": "Start Odoo in debug mode",
                "type": "process",
                "command": "invoke",
                "args": ["start", "--detach", "--debugpy"],
                "presentation": {
                    "echo": True,
                    "reveal": "silent",
                    "focus": False,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {"statusbar": {"hide": True}},
            },
            {
                "label": "Stop Odoo",
                "type": "process",
                "command": "invoke",
                "args": ["stop"],
                "presentation": {
                    "echo": True,
                    "reveal": "silent",
                    "focus": False,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {"statusbar": {"label": "$(stop-circle)"}},
            },
        ],
    }
    # Sort project folders
    cw_config["folders"].sort(key=lambda x: x["path"])
    # Put Odoo folder just before private and top folder
    odoo = SRC_PATH / "odoo"
    if odoo.is_dir():
        cw_config["folders"].append({"path": str(odoo.relative_to(PROJECT_ROOT))})
    # HACK https://github.com/microsoft/vscode/issues/95963 put private second to last
    private = SRC_PATH / "private"
    if private.is_dir():
        cw_config["folders"].append({"path": str(private.relative_to(PROJECT_ROOT))})
    # HACK https://github.com/microsoft/vscode/issues/37947 put top folder last
    cw_config["folders"].append({"path": ".", "name": root_name})
    with open(cw_path, "w") as cw_fd:
        json.dump(cw_config, cw_fd, indent=2)
        cw_fd.write("\n")


@task
def develop(c):
    """Set up a basic development environment."""
    # Prepare environment
    Path(PROJECT_ROOT, "odoo", "auto", "addons").mkdir(parents=True, exist_ok=True)
    with c.cd(str(PROJECT_ROOT)):
        c.run("git init")
        c.run("ln -sf devel.yaml docker-compose.yml")
        write_code_workspace_file(c)
        c.run("pre-commit install")


@task(develop)
def git_aggregate(c):
    """Download odoo & addons git code.

    Executes git-aggregator from within the doodba container.
    """
    with c.cd(str(PROJECT_ROOT)):
        c.run(
            "docker-compose --file setup-devel.yaml run --rm odoo",
            env=UID_ENV,
        )
    write_code_workspace_file(c)
    for git_folder in SRC_PATH.glob("*/.git/.."):
        action = (
            "install"
            if (git_folder / ".pre-commit-config.yaml").is_file()
            else "uninstall"
        )
        with c.cd(str(git_folder)):
            c.run(f"pre-commit {action}")


@task(develop)
def img_build(c, pull=True):
    """Build docker images."""
    cmd = "docker-compose build"
    if pull:
        cmd += " --pull"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd, env=UID_ENV)


@task(develop)
def img_pull(c):
    """Pull docker images."""
    with c.cd(str(PROJECT_ROOT)):
        c.run("docker-compose pull")


@task(develop)
def lint(c, verbose=False):
    """Lint & format source code."""
    cmd = "pre-commit run --show-diff-on-failure --all-files --color=always"
    if verbose:
        cmd += " --verbose"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd)


@task(develop)
def start(c, detach=True, debugpy=False):
    """Start environment."""
    cmd = "docker-compose up"
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
    ) as tmp_docker_compose_file:
        if debugpy:
            # Remove auto-reload
            cmd = (
                "docker-compose -f docker-compose.yml "
                f"-f {tmp_docker_compose_file.name} up"
            )
            _remove_auto_reload(
                tmp_docker_compose_file,
                orig_file=PROJECT_ROOT / "docker-compose.yml",
            )
        if detach:
            cmd += " --detach"
        with c.cd(str(PROJECT_ROOT)):
            c.run(cmd, env=dict(UID_ENV, DOODBA_DEBUGPY_ENABLE=str(int(debugpy))))
        _logger.info("Waiting for services to spin up...")
        time.sleep(SERVICES_WAIT_TIME)


@task(
    develop,
    help={
        "modules": "Comma-separated list of modules to install.",
        "core": "Install all core addons. Default: False",
        "extra": "Install all extra addons. Default: False",
        "private": "Install all private addons. Default: False",
    },
)
def install(c, modules=None, core=False, extra=False, private=False):
    """Install Odoo addons

    By default, installs addon from directory being worked on,
    unless other options are specified.
    """
    if not (modules or core or extra or private):
        cur_module = _get_cwd_addon(Path.cwd())
        if not cur_module:
            raise exceptions.ParseError(
                msg="You must provide at least one option for modules"
                " or be in a subdirectory of one."
                " See --help for details."
            )
        modules = cur_module
    cmd = "docker-compose run --rm odoo addons init"
    if core:
        cmd += " --core"
    if extra:
        cmd += " --extra"
    if private:
        cmd += " --private"
    if modules:
        cmd += f" -w {modules}"
    with c.cd(str(PROJECT_ROOT)):
        c.run(
            cmd,
            env=dict(
                UID_ENV,
            ),
        )


@task(
    develop,
    help={
        "modules": "Comma-separated list of modules to test.",
        "debugpy": "Whether or not to run tests in a VSCode debugging session. "
        "Default: False",
        "cur-file": "Path to the current file."
        " Addon name will be obtained from there to run tests",
        "mode": "Mode in which tests run. Options: ['init'(default), 'update']",
    },
)
def test(c, modules=None, debugpy=False, cur_file=None, mode="init"):
    """Run Odoo tests

    By default, tests addon from directory being worked on,
    unless other options are specified.

    NOTE: Odoo must be restarted manually after this to go back to normal mode
    """
    if not modules:
        cur_module = _get_cwd_addon(cur_file or Path.cwd())
        if not cur_module:
            raise exceptions.ParseError(
                msg="You must provide at least one option for modules/file. "
                "See --help for details."
            )
        else:
            modules = cur_module
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml"
    ) as tmp_docker_compose_file:
        cmd = (
            "docker-compose -f docker-compose.yml "
            f"-f {tmp_docker_compose_file.name} up -d"
        )
        odoo_command = ["odoo", "--test-enable", "--stop-after-init", "--workers=0"]
        if mode == "init":
            odoo_command.append("-i")
        elif mode == "update":
            odoo_command.append("-u")
        else:
            raise exceptions.ParseError(
                msg="Available modes are 'init' or 'update'." " See --help for details."
            )
        odoo_command.append(modules)
        _override_docker_command(
            "odoo",
            odoo_command,
            file=tmp_docker_compose_file,
            orig_file=Path(str(PROJECT_ROOT), "docker-compose.yml"),
        )
        with c.cd(str(PROJECT_ROOT)):
            c.run(
                cmd,
                env=dict(
                    UID_ENV,
                    DOODBA_DEBUGPY_ENABLE=str(int(debugpy)),
                ),
            )
        _logger.info("Waiting for services to spin up...")
        time.sleep(SERVICES_WAIT_TIME)


@task(
    develop,
    help={"purge": "Remove all related containers, networks images and volumes"},
)
def stop(c, purge=False):
    """Stop and (optionally) purge environment."""
    cmd = "docker-compose"
    if purge:
        cmd += " down --remove-orphans --rmi local --volumes"
    else:
        cmd += " stop"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd)


@task(
    develop,
    help={
        "dbname": "The DB that will be DESTROYED and recreated. Default: 'devel'.",
        "modules": "Comma-separated list of modules to install. Default: 'base'.",
    },
)
def resetdb(c, modules="base", dbname="devel"):
    """Reset the specified database with the specified modules.

    Uses click-odoo-initdb behind the scenes, which has a caching system that
    makes DB resets quicker. See its docs for more info.
    """
    with c.cd(str(PROJECT_ROOT)):
        c.run("docker-compose stop odoo", pty=True)
        _run = "docker-compose run --rm -l traefik.enable=false odoo"
        c.run(
            f"{_run} click-odoo-dropdb {dbname}",
            env=UID_ENV,
            warn=True,
            pty=True,
        )
        c.run(
            f"{_run} click-odoo-initdb -n {dbname} -m {modules}",
            env=UID_ENV,
            pty=True,
        )


@task(develop)
def restart(c, quick=True):
    """Restart odoo container(s)."""
    cmd = "docker-compose restart"
    if quick:
        cmd = f"{cmd} -t0"
    cmd = f"{cmd} odoo odoo_proxy"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd, env=UID_ENV)


@task(develop)
def logs(c, tail=10, follow=True):
    """Obtain last logs of current environment."""
    cmd = "docker-compose logs"
    if follow:
        cmd += " -f"
    if tail:
        cmd += f" --tail {tail}"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd)
