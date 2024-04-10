"""Doodba child project tasks.

This file is to be executed with https://www.pyinvoke.org/ in Python 3.8.1+.

Contains common helpers to develop using this child project.
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import datetime
from itertools import chain
from logging import getLogger
from pathlib import Path
from shutil import which

from invoke import exceptions, task

try:
    import yaml
except ImportError:
    from invoke.util import yaml

PROJECT_ROOT = Path(__file__).parent.absolute()
SRC_PATH = PROJECT_ROOT / "odoo" / "custom" / "src"
UID_ENV = {
    "GID": os.environ.get("DOODBA_GID", str(os.getgid())),
    "UID": os.environ.get("DOODBA_UID", str(os.getuid())),
    "DOODBA_UMASK": os.environ.get("DOODBA_UMASK", "27"),
}
UID_ENV.update(
    {
        "DOODBA_GITAGGREGATE_GID": os.environ.get(
            "DOODBA_GITAGGREGATE_GID", UID_ENV["GID"]
        ),
        "DOODBA_GITAGGREGATE_UID": os.environ.get(
            "DOODBA_GITAGGREGATE_UID", UID_ENV["UID"]
        ),
    }
)
SERVICES_WAIT_TIME = int(os.environ.get("SERVICES_WAIT_TIME", 4))
ODOO_VERSION = float(
    yaml.safe_load((PROJECT_ROOT / "common.yaml").read_text())["services"]["odoo"][
        "build"
    ]["args"]["ODOO_VERSION"]
)
# Depending on the user's docker version either version of docker compose could not
# be available. We default to v2 and fallback to v1.

docker_compose_v2 = (
    subprocess.run([shutil.which("docker"), "compose"], capture_output=True).returncode
    == 0
)
DOCKER_COMPOSE_CMD = (
    f"{shutil.which('docker')} compose"
    if docker_compose_v2
    else shutil.which("docker-compose")
)

_logger = getLogger(__name__)


def _override_docker_command(service, command, file, orig_file=None):
    # Read config from main file
    if orig_file:
        with open(orig_file) as fd:
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
    with open(orig_file) as fd:
        orig_docker_config = yaml.safe_load(fd.read())
    odoo_command = orig_docker_config["services"]["odoo"]["command"]
    new_odoo_command = []
    for flag in odoo_command:
        if flag.startswith("--dev"):
            flag = flag.replace("reload,", "")
        new_odoo_command.append(flag)
    _override_docker_command("odoo", new_odoo_command, file, orig_file=orig_file)


def _get_cwd_addon(file):
    cwd = Path(file).resolve()
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
    root_var = "${workspaceFolder:%s}" % root_name
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
    # Static settings
    cw_config.setdefault("settings", {})
    cw_config["settings"].update(
        {
            "python.autoComplete.extraPaths": [f"{str(SRC_PATH)}/odoo"],
            "python.formatting.provider": "none",
            "python.linting.flake8Enabled": True,
            "python.linting.ignorePatterns": [f"{str(SRC_PATH)}/odoo/**/*.py"],
            "python.linting.pylintArgs": [
                f"--init-hook=\"import sys;sys.path.append('{str(SRC_PATH)}/odoo')\"",
                "--load-plugins=pylint_odoo",
            ],
            "python.linting.pylintEnabled": True,
            "python.defaultInterpreterPath": "python%s"
            % (2 if ODOO_VERSION < 11 else 3),
            "restructuredtext.confPath": "",
            "search.followSymlinks": False,
            "search.useIgnoreFiles": False,
            # Language-specific configurations
            "[python]": {"editor.defaultFormatter": "ms-python.black-formatter"},
            "[json]": {"editor.defaultFormatter": "esbenp.prettier-vscode"},
            "[jsonc]": {"editor.defaultFormatter": "esbenp.prettier-vscode"},
            "[markdown]": {"editor.defaultFormatter": "esbenp.prettier-vscode"},
            "[yaml]": {"editor.defaultFormatter": "esbenp.prettier-vscode"},
            "[xml]": {"editor.formatOnSave": False},
        }
    )
    # Launch configurations
    debugpy_configuration = {
        "name": "Attach Python debugger to running container",
        "type": "python",
        "request": "attach",
        "pathMappings": [],
        "port": int(ODOO_VERSION) * 1000 + 899,
        # HACK https://github.com/microsoft/vscode-python/issues/14820
        "host": "0.0.0.0",
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
                "name": "Test and debug current module",
                "configurations": ["Attach Python debugger to running container"],
                "preLaunchTask": "Run Odoo Tests in debug mode for current module",
                "internalConsoleOptions": "openOnSessionStart",
            },
        ],
        "configurations": [
            debugpy_configuration,
            firefox_configuration,
            chrome_configuration,
        ],
    }
    # Configure folders and debuggers
    debugpy_configuration["pathMappings"].append(
        {
            "localRoot": "${workspaceFolder:odoo}/",
            "remoteRoot": "/opt/odoo/custom/src/odoo",
        }
    )
    cw_config["folders"] = []
    for subrepo in SRC_PATH.glob("*"):
        if not subrepo.is_dir():
            continue
        if (subrepo / ".git").exists() and subrepo.name != "odoo":
            cw_config["folders"].append(
                {"path": str(subrepo.relative_to(PROJECT_ROOT))}
            )
        for addon in chain(subrepo.glob("*"), subrepo.glob("addons/*")):
            if (addon / "__manifest__.py").is_file() or (
                addon / "__openerp__.py"
            ).is_file():
                if subrepo.name == "odoo":
                    # ruff: noqa: UP031
                    local_path = "${workspaceFolder:%s}/addons/%s/" % (
                        subrepo.name,
                        addon.name,
                    )
                else:
                    local_path = "${workspaceFolder:%s}/%s" % (subrepo.name, addon.name)
                debugpy_configuration["pathMappings"].append(
                    {
                        "localRoot": local_path,
                        "remoteRoot": f"/opt/odoo/auto/addons/{addon.name}/",
                    }
                )
                url = f"http://localhost:{ODOO_VERSION:.0f}069/{addon.name}/static/"
                path = "${workspaceFolder:%s}/%s/static/" % (
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
                "options": {"statusbar": {"label": "$(play-circle) Start Odoo"}},
            },
            {
                "label": "Install current module",
                "type": "process",
                "command": "invoke",
                "args": ["install", "--cur-file", "${file}", "restart"],
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": True,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {
                    "statusbar": {"label": "$(symbol-property) Install module"}
                },
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
                "options": {"statusbar": {"label": "$(beaker) Test module"}},
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
                "options": {"statusbar": {"label": "$(stop-circle) Stop Odoo"}},
            },
            {
                "label": "Restart Odoo",
                "type": "process",
                "command": "invoke",
                "args": ["restart"],
                "presentation": {
                    "echo": True,
                    "reveal": "silent",
                    "focus": False,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {"statusbar": {"label": "$(history) Restart Odoo"}},
            },
            {
                "label": "See container logs",
                "type": "process",
                "command": "invoke",
                "args": ["logs"],
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": False,
                    "panel": "shared",
                    "showReuseMessage": True,
                    "clear": False,
                },
                "problemMatcher": [],
                "options": {
                    "statusbar": {"label": "$(list-selection) See container logs"}
                },
            },
        ],
    }
    # Sort project folders
    cw_config["folders"].sort(key=lambda x: x["path"])
    # Put Odoo folder just before private and top folder and map to debugpy
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
    auto = Path(PROJECT_ROOT, "odoo", "auto")
    addons = auto / "addons"
    addons.mkdir(parents=True, exist_ok=True)
    # Allow others writing, for podman support
    auto.chmod(0o777)
    addons.chmod(0o777)
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
            DOCKER_COMPOSE_CMD + " --file setup-devel.yaml run --rm -T odoo",
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
def closed_prs(c):
    """Test closed PRs from repos.yaml"""
    with c.cd(str(PROJECT_ROOT / "odoo/custom/src")):
        cmd = "gitaggregate -c {} show-closed-prs".format("repos.yaml")
        c.run(cmd, env=UID_ENV, pty=True)


@task()
def img_build(c, pull=True):
    """Build docker images."""
    cmd = DOCKER_COMPOSE_CMD + " build"
    if pull:
        cmd += " --pull"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd, env=UID_ENV, pty=True)


@task()
def img_pull(c):
    """Pull docker images."""
    with c.cd(str(PROJECT_ROOT)):
        c.run(DOCKER_COMPOSE_CMD + " pull", pty=True)


@task()
def lint(c, verbose=False):
    """Lint & format source code."""
    cmd = "pre-commit run --show-diff-on-failure --all-files --color=always"
    if verbose:
        cmd += " --verbose"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd)


@task()
def start(c, detach=True, debugpy=False):
    """Start environment."""
    cmd = DOCKER_COMPOSE_CMD + " up"
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
    ) as tmp_docker_compose_file:
        if debugpy:
            # Remove auto-reload
            cmd = (
                DOCKER_COMPOSE_CMD + " -f docker-compose.yml "
                f"-f {tmp_docker_compose_file.name} up"
            )
            _remove_auto_reload(
                tmp_docker_compose_file,
                orig_file=PROJECT_ROOT / "docker-compose.yml",
            )
        if detach:
            cmd += " --detach"
        with c.cd(str(PROJECT_ROOT)):
            result = c.run(
                cmd,
                pty=True,
                env=dict(
                    UID_ENV,
                    DOODBA_DEBUGPY_ENABLE=str(int(debugpy)),
                ),
            )
            if not (
                "Recreating" in result.stdout
                or "Starting" in result.stdout
                or "Creating" in result.stdout
            ):
                restart(c)
        _logger.info("Waiting for services to spin up...")
        time.sleep(SERVICES_WAIT_TIME)


@task(
    help={
        "modules": "Comma-separated list of modules to install.",
        "core": "Install all core addons. Default: False",
        "extra": "Install all extra addons. Default: False",
        "private": "Install all private addons. Default: False",
        "enterprise": "Install all enterprise addons. Default: False",
        "cur-file": "Path to the current file."
        " Addon name will be obtained from there to install.",
    },
)
def install(
    c,
    modules=None,
    cur_file=None,
    core=False,
    extra=False,
    private=False,
    enterprise=False,
):
    """Install Odoo addons

    By default, installs addon from directory being worked on,
    unless other options are specified.
    """
    if not (modules or core or extra or private or enterprise):
        cur_module = _get_cwd_addon(cur_file or Path.cwd())
        if not cur_module:
            raise exceptions.ParseError(
                msg="Odoo addon to install not found. "
                "You must provide at least one option for modules"
                " or be in a subdirectory of one."
                " See --help for details."
            )
        modules = cur_module
    cmd = DOCKER_COMPOSE_CMD + " run --rm odoo addons init"
    if core:
        cmd += " --core"
    if extra:
        cmd += " --extra"
    if private:
        cmd += " --private"
    if enterprise:
        cmd += " --enterprise"
    if modules:
        cmd += f" -w {modules}"
    with c.cd(str(PROJECT_ROOT)):
        c.run(DOCKER_COMPOSE_CMD + " stop odoo")
        c.run(
            cmd,
            env=UID_ENV,
            pty=True,
        )


@task(
    help={
        "modules": "Comma-separated list of modules to uninstall.",
    },
)
def uninstall(
    c,
    modules=None,
    cur_file=None,
):
    """Uninstall Odoo addons

    By default, uninstalls addon from directory being worked on,
    unless other options are specified.
    """
    if not modules:
        cur_module = _get_cwd_addon(cur_file or Path.cwd())
        if not cur_module:
            raise exceptions.ParseError(
                msg="Odoo addon to uninstall not found. "
                "You must provide at least one option for modules"
                " or be in a subdirectory of one."
                " See --help for details."
            )
        modules = cur_module
    cmd = (
        DOCKER_COMPOSE_CMD
        + f" run --rm odoo click-odoo-uninstall -m {modules or cur_module}"
    )
    with c.cd(str(PROJECT_ROOT)):
        c.run(
            cmd,
            env=UID_ENV,
            pty=True,
        )


def _get_module_dependencies(
    c, modules=None, core=False, extra=False, private=False, enterprise=False
):
    """Returns a list of the addons' dependencies

    By default, refers to the addon from directory being worked on,
    unless other options are specified.
    """
    # Get list of dependencies for addon
    cmd = DOCKER_COMPOSE_CMD + " run --rm odoo addons list --dependencies"
    if core:
        cmd += " --core"
    if extra:
        cmd += " --extra"
    if private:
        cmd += " --private"
    if enterprise:
        cmd += " --enterprise"
    if modules:
        cmd += f" -w {modules}"
    with c.cd(str(PROJECT_ROOT)):
        dependencies = c.run(
            cmd,
            env=UID_ENV,
            hide="stdout",
        ).stdout.splitlines()[-1]
    return dependencies


def _test_in_debug_mode(c, odoo_command):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml"
    ) as tmp_docker_compose_file:
        cmd = (
            DOCKER_COMPOSE_CMD + " -f docker-compose.yml "
            f"-f {tmp_docker_compose_file.name} up -d"
        )
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
                    DOODBA_DEBUGPY_ENABLE="1",
                ),
                pty=True,
            )
        _logger.info("Waiting for services to spin up...")
        time.sleep(SERVICES_WAIT_TIME)


def _get_module_list(
    c,
    modules=None,
    core=False,
    extra=False,
    private=False,
    enterprise=False,
    only_installable=True,
):
    """Returns a list of addons according to the passed parameters.

    By default, refers to the addon from directory being worked on,
    unless other options are specified.
    """
    # Get list of dependencies for addon
    cmd = DOCKER_COMPOSE_CMD + " run --rm odoo addons list"
    if core:
        cmd += " --core"
    if extra:
        cmd += " --extra"
    if private:
        cmd += " --private"
    if enterprise:
        cmd += " --enterprise"
    if modules:
        cmd += f" -w {modules}"
    if only_installable:
        cmd += " --installable"
    with c.cd(str(PROJECT_ROOT)):
        module_list = c.run(
            cmd,
            env=UID_ENV,
            pty=True,
            hide="stdout",
        ).stdout.splitlines()[-1]
    return module_list


@task(
    help={
        "modules": "Comma-separated list of modules to test.",
        "core": "Test all core addons. Default: False",
        "extra": "Test all extra addons. Default: False",
        "private": "Test all private addons. Default: False",
        "enterprise": "Test all enterprise addons. Default: False",
        "skip": "List of addons to skip. Default: []",
        "debugpy": "Whether or not to run tests in a VSCode debugging session. "
        "Default: False",
        "cur-file": "Path to the current file."
        " Addon name will be obtained from there to run tests",
        "mode": "Mode in which tests run. Options: ['init'(default), 'update']",
        "db_filter": "DB_FILTER regex to pass to the test container Set to ''"
        " to disable. Default: '^devel$'",
    },
)
def test(
    c,
    modules=None,
    core=False,
    extra=False,
    private=False,
    enterprise=False,
    skip="",
    debugpy=False,
    cur_file=None,
    mode="init",
    db_filter="^devel$",
):
    """Run Odoo tests

    By default, tests addon from directory being worked on,
    unless other options are specified.

    NOTE: Odoo must be restarted manually after this to go back to normal mode
    """
    if not (modules or core or extra or private or enterprise):
        cur_module = _get_cwd_addon(cur_file or Path.cwd())
        if not cur_module:
            raise exceptions.ParseError(
                msg="Odoo addon to install not found. "
                "You must provide at least one option for modules"
                " or be in a subdirectory of one."
                " See --help for details."
            )
        modules = cur_module
    else:
        modules = _get_module_list(c, modules, core, extra, private, enterprise)
    odoo_command = ["odoo", "--test-enable", "--stop-after-init", "--workers=0"]
    if mode == "init":
        odoo_command.append("-i")
    elif mode == "update":
        odoo_command.append("-u")
    else:
        raise exceptions.ParseError(
            msg="Available modes are 'init' or 'update'. See --help for details."
        )
    # Skip test in some modules
    modules_list = modules.split(",")
    for m_to_skip in skip.split(","):
        if not m_to_skip:
            continue
        if m_to_skip not in modules_list:
            _logger.warn(
                "%s not found in the list of addons to test: %s", (m_to_skip, modules)
            )
        modules_list.remove(m_to_skip)
    modules = ",".join(modules_list)
    odoo_command.append(modules)
    if ODOO_VERSION >= 12:
        # Limit tests to explicit list
        # Filter spec format (comma-separated)
        # [-][tag][/module][:class][.method]
        odoo_command.extend(["--test-tags", f"/{',/'.join(modules_list)}"])
    if debugpy:
        _test_in_debug_mode(c, odoo_command)
    else:
        cmd = [DOCKER_COMPOSE_CMD, "run", "--rm"]
        if db_filter:
            cmd.extend(["-e", f"DB_FILTER='{db_filter}'"])
        cmd.append("odoo")
        cmd.extend(odoo_command)
        with c.cd(str(PROJECT_ROOT)):
            c.run(
                " ".join(cmd),
                env=UID_ENV,
                pty=True,
            )


@task(
    help={"purge": "Remove all related containers, networks images and volumes"},
)
def stop(c, purge=False):
    """Stop and (optionally) purge environment."""
    cmd = f"{DOCKER_COMPOSE_CMD} down --remove-orphans"
    if purge:
        cmd += " --rmi local --volumes"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd, pty=True)


@task(
    help={
        "dbname": "The DB that will be DESTROYED and recreated. Default: 'devel'.",
        "modules": "Comma-separated list of modules to install. Default: 'base'.",
        "core": "Install all core addons. Default: False",
        "extra": "Install all extra addons. Default: False",
        "private": "Install all private addons. Default: False",
        "enterprise": "Install all enterprise addons. Default: False",
        "populate": "Run preparedb task right after (only available for v11+)."
        " Default: True",
        "dependencies": "Install only the dependencies of the specified addons."
        "Default: False",
    },
)
def resetdb(
    c,
    modules=None,
    core=False,
    extra=False,
    private=False,
    enterprise=False,
    dbname="devel",
    populate=True,
    dependencies=False,
):
    """Reset the specified database with the specified modules.

    Uses click-odoo-initdb behind the scenes, which has a caching system that
    makes DB resets quicker. See its docs for more info.
    """
    if dependencies:
        modules = _get_module_dependencies(c, modules, core, extra, private, enterprise)
    elif core or extra or private or enterprise:
        modules = _get_module_list(c, modules, core, extra, private, enterprise)
    else:
        modules = modules or "base"
    with c.cd(str(PROJECT_ROOT)):
        c.run(f"{DOCKER_COMPOSE_CMD} stop odoo", pty=True)
        _run = f"{DOCKER_COMPOSE_CMD} run --rm -l traefik.enable=false odoo"
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
    if populate and ODOO_VERSION < 11:
        _logger.warn(
            f"Skipping populate task as it is not available in v{ODOO_VERSION}"
        )
        populate = False
    if populate:
        preparedb(c)


@task()
def preparedb(c):
    """Run the `preparedb` script inside the container

    Populates the DB with some helpful config
    """
    if ODOO_VERSION < 11:
        raise exceptions.PlatformError(
            "The preparedb script is not available for Doodba environments bellow v11."
        )
    with c.cd(str(PROJECT_ROOT)):
        c.run(
            f"{DOCKER_COMPOSE_CMD} run --rm -l traefik.enable=false odoo preparedb",
            env=UID_ENV,
            pty=True,
        )


@task()
def restart(c, quick=True):
    """Restart odoo container(s)."""
    cmd = f"{DOCKER_COMPOSE_CMD} restart"
    if quick:
        cmd = f"{cmd} -t0"
    cmd = f"{cmd} odoo odoo_proxy"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd, env=UID_ENV, pty=True)


@task(
    help={
        "container": "Names of the containers from which logs will be obtained."
        " You can specify a single one, or several comma-separated names."
        " Default: None (show logs for all containers)"
    },
)
def logs(c, tail=10, follow=True, container=None):
    """Obtain last logs of current environment."""
    cmd = f"{DOCKER_COMPOSE_CMD} logs"
    if follow:
        cmd += " -f"
    if tail:
        cmd += f" --tail {tail}"
    if container:
        cmd += f" {container.replace(',', ' ')}"
    with c.cd(str(PROJECT_ROOT)):
        c.run(cmd, pty=True)


@task
def after_update(c):
    """Execute some actions after a copier update or init"""
    # Make custom build scripts executable
    if ODOO_VERSION < 11:
        files = (
            Path(PROJECT_ROOT, "odoo", "custom", "build.d", "20-update-pg-repos"),
            Path(PROJECT_ROOT, "odoo", "custom", "build.d", "10-fix-certs"),
        )
        for script_file in files:
            # Ignore if, for some reason, the file didn't end up in the generated
            # project despite of the correct version (e.g. Copier exclusions)
            if not script_file.exists():
                continue
            cur_stat = script_file.stat()
            # Like chmod ug+x
            script_file.chmod(cur_stat.st_mode | stat.S_IXUSR | stat.S_IXGRP)
    else:
        # Remove version-specific build scripts if the copier update didn't
        # HACK: https://github.com/copier-org/copier/issues/461
        files = (
            Path(PROJECT_ROOT, "odoo", "custom", "build.d", "20-update-pg-repos"),
            Path(PROJECT_ROOT, "odoo", "custom", "build.d", "10-fix-certs"),
        )
        for script_file in files:
            # missing_ok argument would take care of this, but it was only added for
            # Python 3.8
            if script_file.exists():
                script_file.unlink()


@task(
    help={
        "source_db": "The source DB name. Default: 'devel'.",
        "destination_db": (
            "The destination DB name. Default: '[SOURCE_DB_NAME]-[CURRENT_DATE]'"
        ),
    },
)
def snapshot(
    c,
    source_db="devel",
    destination_db=None,
):
    """Snapshot current database and filestore.

    Uses click-odoo-copydb behind the scenes to make a snapshot.
    """
    if not destination_db:
        destination_db = f"{source_db}-{datetime.now().strftime('%Y_%m_%d-%H_%M')}"
    with c.cd(str(PROJECT_ROOT)):
        cur_state = c.run(f"{DOCKER_COMPOSE_CMD} stop odoo db", pty=True).stdout
        _logger.info("Snapshoting current %s DB to %s", (source_db, destination_db))
        _run = f"{DOCKER_COMPOSE_CMD} run --rm -l traefik.enable=false odoo"
        c.run(
            f"{_run} click-odoo-copydb {source_db} {destination_db}",
            env=UID_ENV,
            pty=True,
        )
        if "Stopping" in cur_state:
            # Restart services if they were previously active
            c.run(f"{DOCKER_COMPOSE_CMD} start odoo db", pty=True)


@task(
    help={
        "snapshot_name": "The snapshot name. If not provided,"
        "the script will try to find the last snapshot"
        " that starts with the destination_db name",
        "destination_db": "The destination DB name. Default: 'devel'",
    },
)
def restore_snapshot(
    c,
    snapshot_name=None,
    destination_db="devel",
):
    """Restore database and filestore snapshot.

    Uses click-odoo-copydb behind the scenes to restore a DB snapshot.
    """
    with c.cd(str(PROJECT_ROOT)):
        cur_state = c.run(f"{DOCKER_COMPOSE_CMD} stop odoo db", pty=True).stdout
        if not snapshot_name:
            # List DBs
            res = c.run(
                f"{DOCKER_COMPOSE_CMD} run --rm -e LOG_LEVEL=WARNING odoo psql -tc"
                " 'SELECT datname FROM pg_database;'",
                env=UID_ENV,
                hide="stdout",
            )
            db_list = []
            for db in res.stdout.splitlines():
                # Parse and filter DB List
                if not db.lstrip().startswith(destination_db):
                    continue
                db_name = db.lstrip()
                try:
                    db_date = datetime.strptime(
                        db_name.lstrip(f"{destination_db}-"), "%Y_%m_%d-%H_%M"
                    )
                    db_list.append((db_name, db_date))
                except ValueError:
                    continue
            snapshot_name = max(db_list, key=lambda x: x[1])[0]
            if not snapshot_name:
                raise exceptions.PlatformError(
                    "No snapshot found for destination_db %s" % destination_db
                )
        _logger.info("Restoring snapshot %s to %s", (snapshot_name, destination_db))
        _run = f"{DOCKER_COMPOSE_CMD} run --rm -l traefik.enable=false odoo"
        c.run(
            f"{_run} click-odoo-dropdb {destination_db}",
            env=UID_ENV,
            warn=True,
            pty=True,
        )
        c.run(
            f"{_run} click-odoo-copydb {snapshot_name} {destination_db}",
            env=UID_ENV,
            pty=True,
        )
        if "Stopping" in cur_state:
            c.run(f"{DOCKER_COMPOSE_CMD} start odoo db", pty=True)
