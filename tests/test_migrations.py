from glob import glob
from pathlib import Path

from copier import run_update
from plumbum import local
from plumbum.cmd import git, invoke

from .conftest import DBVER_PER_ODOO

OLDEST_TEMPLATE_VERSION = "v0.1.0"

# Notes:
# - Template versions before 5.1.4 are not compatible with latest pyhton versions (pre-commit regex issue).
# - Template versions before 3.0.0 are not compatible with latest copier versions ('postgres_version' question has invalid choice type).
# - copier-answers before 5.2.0 are not compatible with latest copier versions (null answers are not supported for some question types).


def test_transtion_to_copier(
    tmp_path: Path, cloned_template: Path, supported_odoo_version: float
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
            "ODOO_MAJOR=11", f"ODOO_MAJOR={int(supported_odoo_version)}"
        )
        env_contents = env_contents.replace(
            "ODOO_MINOR=11.0", f"ODOO_MINOR={supported_odoo_version:.1f}"
        )
        env_contents = env_contents.replace(
            "ODOO_IMAGE=docker.io/myuser/myproject-odoo",
            "ODOO_IMAGE=registry.example.com/custom-team/custom-project-odoo",
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
        answers_file_contents = answers_file_contents.replace(
            "_commit: v0.0.0-0-0",
            f"_commit: {OLDEST_TEMPLATE_VERSION}",
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
        dbver = DBVER_PER_ODOO[supported_odoo_version]["latest"]
        run_update(
            dst_path=str(tmp_path),
            data={
                "odoo_version": supported_odoo_version,
                "postgres_version": dbver,
            },
            user_defaults={
                "gitlab_host": "",
                "domain_prod": "",
                "domain_prod_alternatives": "",
                "domain_test": "",
                "odoo_oci_image": "registry.example.com/custom-team/custom-project-odoo",
                "smtp_default_from": "",
                "smtp_relay_host": "",
                "smtp_relay_user": "",
                "smtp_canonical_default": "",
                "smtp_canonical_domains": "",
                "backup_dst": "",
                "backup_email_from": "",
                "backup_email_to": "",
                "backup_deletion": False,
                "backup_aws_access_key_id": "",
                "backup_aws_secret_access_key": "",
            },
            vcs_ref=tag,
            defaults=True,
            overwrite=True,
            unsafe=True,
        )
        # Check migrations ran fine
        # env file was removed in 'update_domains_structure' migration script
        assert not env_file.exists()
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
