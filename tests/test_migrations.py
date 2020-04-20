from glob import glob
from pathlib import Path

from copier import copy
from plumbum import local
from plumbum.cmd import git, invoke

LATEST_VERSION_WITHOUT_COPIER = "v0.0.0"


def test_transtion_to_copier(
    tmp_path: Path, cloned_template: Path, any_odoo_version: float
):
    """Test transition from old git-clone-based workflow to new copier-based."""
    tag = "v999999.99.99"
    with local.cwd(cloned_template):
        git("tag", "--delete", "test")
        git("tag", "--force", tag)
    # Emulate user cloning scaffolding using the old workflow
    git("clone", "https://github.com/Tecnativa/doodba-scaffolding", tmp_path)
    with local.cwd(tmp_path):
        # Emulate user modifying some basic variables and committing
        env_file = tmp_path / ".env"
        env_contents = env_file.read_text()
        env_contents = env_contents.replace(
            "ODOO_MAJOR=11", f"ODOO_MAJOR={int(any_odoo_version)}"
        )
        env_contents = env_contents.replace(
            "ODOO_MINOR=11.0", f"ODOO_MINOR={any_odoo_version:.1f}"
        )
        env_contents = env_contents.replace(
            "ODOO_IMAGE=docker.io/myuser/myproject-odoo",
            f"ODOO_IMAGE=registry.example.com/custom-team/custom-project-odoo",
        )
        env_file.write_text(env_contents)
        addons_file = tmp_path / "odoo" / "custom" / "src" / "addons.yaml"
        addons_file.write_text('server-tools: ["*"]')
        assert 'server-tools: ["*"]' in addons_file.read_text()
        answers_file = tmp_path / ".copier-answers.yml"
        answers_file_contents = answers_file.read_text()
        answers_file_contents = answers_file_contents.replace(
            "_src_path: https://github.com/Tecnativa/doodba-copier-template.git",
            f"_src_path: {cloned_template}",
        )
        answers_file.write_text(answers_file_contents)
        assert f"_src_path: {cloned_template}" in answers_file.read_text()
        dep_files = glob(str(tmp_path / "odoo" / "custom" / "dependencies" / "*.txt"))
        assert len(dep_files) == 5
        for dep_file in map(Path, dep_files):
            with dep_file.open("a") as dep_fd:
                dep_fd.write("\n# a comment")
        git("add", ".")
        git("commit", "-m", "update")
        # Emulate user upgrading to copier, passing the right variables
        copy(
            dst_path=str(tmp_path),
            force=True,
            data={
                "odoo_version": any_odoo_version,
                "odoo_oci_image": "registry.example.com/custom-team/custom-project-odoo",
            },
            vcs_ref=tag,
        )
        env_contents = env_file.read_text()
        assert f"ODOO_MAJOR={int(any_odoo_version)}" in env_contents
        assert f"ODOO_MINOR={any_odoo_version:.1f}" in env_contents
        assert (tmp_path / ".copier-answers.yml").is_file()
        assert 'server-tools: ["*"]' in addons_file.read_text()
        for dep_file in map(Path, dep_files):
            assert dep_file.read_text().endswith("\n# a comment")
        # Check migrations ran fine
        assert not (tmp_path / ".travis.yml").exists()
        assert not (tmp_path / ".vscode" / "doodba").exists()
        assert not (tmp_path / ".vscode" / "doodbasetup.py").exists()
        assert not (
            tmp_path / "odoo" / "custom" / "src" / "private" / ".empty"
        ).exists()
        # Ensure migrations are resilient to subproject changes
        invoke(
            "--search-root",
            cloned_template,
            "--collection",
            "migrations",
            "from-doodba-scaffolding-to-copier",
        )


def test_v1_5_2_migration(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
):
    """Test migration to v1.5.2."""
    auto = tmp_path / "odoo" / "auto"
    empty = auto / ".empty"  # This file existed in doodba-scaffolding
    with local.cwd(tmp_path):
        # Copy v1.5.1
        copy(src_path=str(cloned_template), vcs_ref="v1.5.1", force=True)
        auto.mkdir()
        empty.touch()
        assert empty.exists()
        git("add", ".")
        git("add", "-f", empty)
        git("commit", "-am", "reformat", retcode=1)
        git("commit", "-am", "copied from template in v1.5.1")
        # Update to v1.5.2
        copy(vcs_ref="v1.5.2", force=True)
        assert not empty.exists()
        assert not auto.exists()
        invoke("develop")
        assert auto.exists()
        assert not empty.exists()


def test_v1_5_3_migration(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
):
    """Test migration to v1.5.3."""
    auto_addons = tmp_path / "odoo" / "auto" / "addons"
    # This part makes sense only when v1.5.3 is not yet released
    with local.cwd(cloned_template):
        if "v1.5.3" not in git("tag").split():
            git("tag", "-d", "test")
            git("tag", "v1.5.3")
    with local.cwd(tmp_path):
        # Copy v1.5.2
        copy(src_path=str(cloned_template), vcs_ref="v1.5.2", force=True)
        assert not auto_addons.exists()
        git("add", ".")
        git("commit", "-am", "reformat", retcode=1)
        git("commit", "-am", "copied from template in v1.5.2")
        # Update to v1.5.3
        copy(vcs_ref="v1.5.3", force=True)
        assert not auto_addons.exists()
        invoke("develop")
        assert auto_addons.is_dir()
        # odoo/auto/addons dir must be writable
        (auto_addons / "sample").touch()
