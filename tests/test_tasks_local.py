import importlib.util
import sys
from pathlib import Path

import pytest
from copier import run_copy, run_update
from plumbum import local
from plumbum.cmd import git

LOCAL_TASK = """\
from invoke import task


@task
def logs(c):
    \"\"\"Local override marker.\"\"\"
"""

TASK_NAME = "logs"


@pytest.fixture
def rendered_project(cloned_template: Path, single_project_path: Path) -> Path:
    """Render a project with a clean Git repo, ready for `copier update`."""
    run_copy(
        src_path=str(cloned_template),
        dst_path=".",
        vcs_ref="test",
        defaults=True,
        overwrite=True,
        unsafe=True,
    )
    git("init", "-q")
    git("add", ".")
    git("commit", "--author=Test<test@test>", "--no-verify", "-qm", "initial render")
    return single_project_path


def _change_template_tasks_local(cloned_template: Path, tag: str):
    """Add a new template version that changes the project-owned file."""
    template_path = Path(cloned_template)
    with local.cwd(template_path):
        upstream_file = template_path / "template" / "tasks_local.py"
        upstream_file.write_text(
            "# Upstream change that must not reach the project\n"
            + upstream_file.read_text()
        )
        git("add", "template/tasks_local.py")
        git(
            "commit",
            "--author=Test<test@test>",
            "--no-verify",
            "-qm",
            "upstream tasks_local change",
        )
        git("tag", tag)


def _load_tasks(project_path: Path, monkeypatch):
    """Import the rendered project's tasks.py the way invoke does."""
    for name in ("tasks", "tasks_local"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.syspath_prepend(str(project_path))
    spec = importlib.util.spec_from_file_location("tasks", project_path / "tasks.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "tasks", module)
    spec.loader.exec_module(module)
    return module


def test_tasks_local_survives_update_and_overrides(
    cloned_template: Path, rendered_project: Path, monkeypatch
):
    """A project-owned task survives `copier update` and overrides the template."""
    tasks_local = rendered_project / "tasks_local.py"
    tasks_local.write_text(LOCAL_TASK)
    git("add", str(tasks_local))
    git("commit", "--no-verify", "-qm", "local task")
    # Make the upstream template change the same file, so update has something
    # to write there. Without `skip_if_exists` it would clobber the local task.
    _change_template_tasks_local(cloned_template, "test2")

    run_update(
        dst_path=str(rendered_project),
        vcs_ref="test2",
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )

    # `tasks_local.py` must be left byte-for-byte untouched by copier
    assert tasks_local.read_text() == LOCAL_TASK
    # The local task must win over the template's same-named task
    tasks = _load_tasks(rendered_project, monkeypatch)
    assert getattr(tasks, TASK_NAME).body.__module__ == "tasks_local"
    assert "Local override marker" in getattr(tasks, TASK_NAME).body.__doc__
