from glob import glob
from pathlib import Path

import pytest
from copier import copy
from plumbum import local
from plumbum.cmd import git

from .helpers import ALL_ODOO_VERSIONS, clone_self_dirty

LATEST_VERSION_WITHOUT_COPIER = "v0.0.0"


@pytest.mark.parametrize("odoo_version", ALL_ODOO_VERSIONS)
def test_transtion_to_copier(tmpdir, odoo_version):
    """Test transition from old git-clone-based workflow to new copier-based."""
    old, tpl = tmpdir / "old", tmpdir / "tpl"
    tag = "v999999.99.99"
    clone_self_dirty(tpl, tag=tag)
    # Emulate user cloning scaffolding using the old workflow
    git("clone", "-bcopier", "https://github.com/Tecnativa/doodba-scaffolding", old)
    with local.cwd(old):
        # Emulate user modifying some basic variables and committing
        env_file = old / ".env"
        env_contents = env_file.read()
        env_contents = env_contents.replace(
            "ODOO_MAJOR=11", f"ODOO_MAJOR={int(odoo_version)}"
        )
        env_contents = env_contents.replace(
            "ODOO_MINOR=11.0", f"ODOO_MINOR={odoo_version:.1f}"
        )
        env_contents = env_contents.replace(
            "ODOO_IMAGE=docker.io/myuser/myproject-odoo",
            f"ODOO_IMAGE=registry.example.com/custom-team/custom-project-odoo",
        )
        env_file.write(env_contents)
        addons_file = old / "odoo" / "custom" / "src" / "addons.yaml"
        addons_file.write('server-tools: ["*"]')
        assert 'server-tools: ["*"]' in addons_file.read()
        answers_file = old / ".copier-answers.yml"
        answers_file_contents = answers_file.read()
        answers_file_contents = answers_file_contents.replace(
            "_src_path: https://github.com/Tecnativa/doodba-copier-template.git",
            f"_src_path: {tpl}",
        )
        answers_file.write(answers_file_contents)
        assert f"_src_path: {tpl}" in answers_file.read()
        dep_files = glob(str(old / "odoo" / "custom" / "dependencies" / "*.txt"))
        assert len(dep_files) == 5
        for dep_file in map(Path, dep_files):
            with dep_file.open("a") as dep_fd:
                dep_fd.write("\n# a comment")
        git("add", ".")
        git("commit", "-m", "update")
        # Emulate user upgrading to copier, passing the right variables
        copy(
            dst_path=str(old),
            force=True,
            data={
                "odoo_version": odoo_version,
                "odoo_oci_image": "registry.example.com/custom-team/custom-project-odoo",
            },
            vcs_ref=tag,
        )
        env_contents = env_file.read()
        assert f"ODOO_MAJOR={int(odoo_version)}" in env_contents
        assert f"ODOO_MINOR={odoo_version:.1f}" in env_contents
        assert (old / ".copier-answers.yml").isfile()
        assert 'server-tools: ["*"]' in addons_file.read()
        for dep_file in map(Path, dep_files):
            assert dep_file.read_text().endswith("\n# a comment")
        # Check migrations ran fine
        assert not (old / ".travis.yml").exists()
        assert not (old / ".vscode" / "doodba").exists()
        assert not (old / ".vscode" / "doodbasetup.py").exists()
        assert not (old / "odoo" / "custom" / "src" / "private" / ".empty").exists()
