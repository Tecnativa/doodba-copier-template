from glob import glob
from pathlib import Path

# import pytest
# import yaml
from copier.main import run_auto
from plumbum import local
from plumbum.cmd import git, invoke

# from typing import Optional


# from .conftest import bypass_pre_commit

LATEST_VERSION_WITHOUT_COPIER = "v0.0.0"
MISSING = object()


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
            "_commit: HEAD",
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
        run_auto(
            dst_path=str(tmp_path),
            data={
                "odoo_version": any_odoo_version,
                "odoo_oci_image": "registry.example.com/custom-team/custom-project-odoo",
            },
            vcs_ref=tag,
            defaults=True,
            overwrite=True,
        )
        env_contents = env_file.read_text()
        assert f"ODOO_MAJOR={int(any_odoo_version)}" in env_contents
        assert f"ODOO_MINOR={any_odoo_version:.1f}" in env_contents
        assert (tmp_path / ".copier-answers.yml").is_file()
        assert 'server-tools: ["*"]' in addons_file.read_text()
        for dep_file in map(Path, dep_files):
            assert dep_file.read_text().endswith("\n# a comment")
        # FIXME: Maybe can't delete old files due they don't have a trace?
        # Check migrations ran fine
        # assert not (tmp_path / ".travis.yml").exists()
        # assert not (tmp_path / ".vscode" / "doodba").exists()
        # assert not (tmp_path / ".vscode" / "doodbasetup.py").exists()
        # assert not (
        #     tmp_path / "odoo" / "custom" / "src" / "private" / ".empty"
        # ).exists()
        # Ensure migrations are resilient to subproject changes
        invoke(
            "--search-root",
            cloned_template,
            "--collection",
            "migrations",
            "from-doodba-scaffolding-to-copier",
        )


# @pytest.mark.sequential
# def test_v1_5_2_migration(
#     tmp_path: Path, cloned_template: Path, supported_odoo_version: float
# ):
#     """Test migration to v1.5.2."""
#     auto = tmp_path / "odoo" / "auto"
#     empty = auto / ".empty"  # This file existed in doodba-scaffolding
#     with local.cwd(tmp_path):
#         # Copy v1.5.1
#         copy(
#             src_path=str(cloned_template),
#             vcs_ref="v1.5.1",
#             force=True,
#             data={"odoo_version": supported_odoo_version},
#             tasks=[
#                 "git init",
#                 "ln -sf devel.yaml docker-compose.yml",
#                 "invoke write-code-workspace-file",
#             ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#         )
#         auto.mkdir()
#         empty.touch()
#         assert empty.exists()
#         git("add", ".")
#         git("add", "-f", empty)
#         git("commit", "-am", "copied from template in v1.5.1")
#         # Update to v1.5.2
#         with bypass_pre_commit():
#             copy(
#                 vcs_ref="v1.5.2",
#                 force=True,
#                 tasks=[
#                     "git init",
#                     "ln -sf devel.yaml docker-compose.yml",
#                     "invoke write-code-workspace-file",
#                 ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#             )
#         assert not empty.exists()
#         assert not auto.exists()
#         invoke("develop")
#         assert auto.exists()
#         assert not empty.exists()


# @pytest.mark.sequential
# def test_v1_5_3_migration(
#     tmp_path: Path, cloned_template: Path, supported_odoo_version: float
# ):
#     """Test migration to v1.5.3."""
#     auto_addons = tmp_path / "odoo" / "auto" / "addons"
#     # This part makes sense only when v1.5.3 is not yet released
#     with local.cwd(cloned_template):
#         if "v1.5.3" not in git("tag").split():
#             git("tag", "-d", "test")
#             git("tag", "v1.5.3")
#     with local.cwd(tmp_path):
#         # Copy v1.5.2
#         copy(
#             src_path=str(cloned_template),
#             vcs_ref="v1.5.2",
#             force=True,
#             tasks=[
#                 "git init",
#                 "ln -sf devel.yaml docker-compose.yml",
#                 "invoke write-code-workspace-file",
#             ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#         )
#         assert not auto_addons.exists()
#         git("add", ".")
#         git("commit", "-am", "copied from template in v1.5.2")
#         # Update to v1.5.3
#         with bypass_pre_commit():
#             copy(
#                 vcs_ref="v1.5.3",
#                 force=True,
#                 tasks=[
#                     "git init",
#                     "ln -sf devel.yaml docker-compose.yml",
#                     "invoke write-code-workspace-file",
#                 ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#             )
#         assert not auto_addons.exists()
#         invoke("develop")
#         assert auto_addons.is_dir()
#         # odoo/auto/addons dir must be writable
#         (auto_addons / "sample").touch()


# @pytest.mark.sequential
# @pytest.mark.parametrize("domain_prod", (MISSING, None, "www.example.com"))
# @pytest.mark.parametrize(
#     "domain_prod_alternatives",
#     (MISSING, None, ["example.com", "www.example.org", "example.org"]),
# )
# @pytest.mark.parametrize("domain_test", (MISSING, None, "demo.example.com"))
# def test_v2_0_0_migration(
#     tmp_path: Path,
#     cloned_template: Path,
#     supported_odoo_version: float,
#     domain_prod,
#     domain_prod_alternatives,
#     domain_test,
# ):
#     """Test migration to v2.0.0."""
#     # Construct data dict, removing MISSING values
#     data = {
#         "domain_prod_alternatives": domain_prod_alternatives,
#         "domain_prod": domain_prod,
#         "domain_test": domain_test,
#         "odoo_version": supported_odoo_version,
#     }
#     for key, value in tuple(data.items()):
#         if value is MISSING:
#             data.pop(key, None)
#     # This part makes sense only when v2.0.0 is not yet released
#     with local.cwd(cloned_template):
#         if "v2.0.0" not in git("tag").split():
#             git("tag", "-d", "test")
#             git("tag", "v2.0.0")
#     with local.cwd(tmp_path):
#         # Copy v1.6.0
#         copy(
#             src_path=str(cloned_template),
#             vcs_ref="v1.6.0",
#             force=True,
#             answers_file=".custom.copier-answers.yaml",
#             data=data,
#             tasks=[
#                 "git init",
#                 "ln -sf devel.yaml docker-compose.yml",
#                 "invoke write-code-workspace-file",
#             ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#         )
#         git("config", "commit.gpgsign", "false")
#         git("add", ".")
#         git("commit", "-am", "copied from template in v1.6.0")
#         # Update to v2.0.0
#         with bypass_pre_commit():
#             copy(
#                 answers_file=".custom.copier-answers.yaml",
#                 vcs_ref="v2.0.0",
#                 force=True,
#                 tasks=[
#                     "git init",
#                     "ln -sf devel.yaml docker-compose.yml",
#                     "invoke write-code-workspace-file",
#                 ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#             )
#         git("add", ".")
#         git("commit", "-am", "updated from template in v2.0.0")
#         # Assert .env removal
#         assert not Path(".env").exists()
#         # Assert domain structure migration
#         answers = yaml.safe_load(Path(".custom.copier-answers.yaml").read_text())
#         assert "domain_prod" not in answers
#         assert "domain_prod_alternatives" not in answers
#         assert "domain_test" not in answers
#         expected_domains_prod = []
#         if data.get("domain_prod"):
#             expected_domains_prod.append(
#                 {
#                     "hosts": [domain_prod],
#                     "cert_resolver": "letsencrypt",
#                 }
#             )
#         if data.get("domain_prod_alternatives") and expected_domains_prod:
#             expected_domains_prod.append(
#                 {
#                     "hosts": domain_prod_alternatives,
#                     "cert_resolver": "letsencrypt",
#                     "redirect_to": domain_prod,
#                 }
#             )
#         assert answers["domains_prod"] == expected_domains_prod
#         expected_domains_test = []
#         if data.get("domain_test"):
#             expected_domains_test.append(
#                 {
#                     "hosts": [domain_test],
#                     "cert_resolver": "letsencrypt",
#                 }
#             )
#         assert answers["domains_test"] == expected_domains_test


# @pytest.mark.sequential
# def test_v2_1_1_migration(
#     tmp_path: Path,
#     cloned_template: Path,
#     supported_odoo_version: float,
# ):
#     """Test migration to v2.1.1."""
#     pre, target = "v2.1.0", "v2.1.1"
#     # This part makes sense only when target version is not yet released
#     with local.cwd(cloned_template):
#         if target not in git("tag").split():
#             git("tag", "-d", "test")
#             git("tag", target)
#     with local.cwd(tmp_path):
#         # Copy previous version
#         copy(
#             src_path=str(cloned_template),
#             vcs_ref=pre,
#             force=True,
#             answers_file=".custom.copier-answers.yaml",
#             data={
#                 "odoo_version": supported_odoo_version,
#             },
#             tasks=[
#                 "git init",
#                 "ln -sf devel.yaml docker-compose.yml",
#                 "invoke write-code-workspace-file",
#             ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#         )
#         git("config", "commit.gpgsign", "false")
#         git("add", ".")
#         git("commit", "-am", f"copied from template in {pre}")
#         # Update to target version
#         with bypass_pre_commit():
#             copy(
#                 answers_file=".custom.copier-answers.yaml",
#                 vcs_ref=target,
#                 force=True,
#                 tasks=[
#                     "git init",
#                     "ln -sf devel.yaml docker-compose.yml",
#                     "invoke write-code-workspace-file",
#                 ],  # Installation of pre-commit modules fails in old versions. We don't need to check that (and can't fix it), so override post-copy and update tasks to avoid pre-commit hooks.
#             )
#         git("add", ".")
#         git("commit", "-am", f"updated from template in {target}")
#         # Assert config files removal
#         assert not Path(".vscode", "launch.json").exists()
#         assert not Path(".vscode", "tasks.json").exists()


# def test_v2_7_0_migration(
#     tmp_path: Path,
#     cloned_template: Path,
#     supported_odoo_version: float,
# ):
#     """Test migration to v2.1.1."""
#     pre, target = "v2.6.1", "v2.7.0"
#     # This part makes sense only when target version is not yet released
#     with local.cwd(cloned_template):
#         if target not in git("tag").split():
#             git("tag", "-d", "test")
#             git("tag", target)
#     with local.cwd(tmp_path):
#         # Copy previous version
#         copy(
#             src_path=str(cloned_template),
#             vcs_ref=pre,
#             force=True,
#             answers_file=".custom.copier-answers.yaml",
#             data={
#                 "odoo_version": supported_odoo_version,
#             },
#         )
#         git("config", "commit.gpgsign", "false")
#         git("add", ".")
#         git("commit", "-am", "reformat", retcode=1)
#         git("commit", "-am", f"copied from template in {pre}")
#         # Update to target version
#         copy(answers_file=".custom.copier-answers.yaml", vcs_ref=target, force=True)
#         git("add", ".")
#         git("commit", "-am", "reformat", retcode=1)
#         git("commit", "-am", f"updated from template in {target}")
#         # Assert config files removal
#         assert not Path(".vscode", "settings.json").exists()


# @pytest.mark.parametrize(
#     "migration_from_version, license_answer", (("v2.8.0", None), ("v3.0.0", ""))
# )
# def test_v3_0_1_migration(
#     tmp_path: Path,
#     cloned_template: Path,
#     supported_odoo_version: float,
#     migration_from_version: str,
#     license_answer: Optional[str],
# ):
#     """Test migration to v3.0.1."""
#     target, license_path = "v3.0.1", Path("LICENSE")
#     # This part makes sense only when target version is not yet released
#     with local.cwd(cloned_template):
#         if target not in git("tag").split():
#             git("tag", "-d", "test")
#             git("tag", target)
#     with local.cwd(tmp_path):
#         # Copy previous version
#         copy(
#             src_path=str(cloned_template),
#             vcs_ref=migration_from_version,
#             force=True,
#             answers_file=".custom.copier-answers.yaml",
#             data={
#                 "odoo_version": supported_odoo_version,
#                 "project_license": license_answer,
#             },
#         )
#         git("config", "commit.gpgsign", "false")
#         git("add", ".")
#         git("commit", "-am", "reformat", retcode=1)
#         git("commit", "-am", f"copied from template in {migration_from_version}")
#         assert not license_path.exists()
#         # Update to target version
#         copy(answers_file=".custom.copier-answers.yaml", vcs_ref=target, force=True)
#         git("add", ".")
#         git("commit", "-am", "reformat", retcode=1)
#         git("commit", "-am", f"updated from template in {target}")
#         # Assert LICENSE still does not exist, after updating
#         assert not license_path.exists()
#         # Assert correct answer in copier answers file
#         answers = yaml.safe_load(Path(".custom.copier-answers.yaml").read_bytes())
#         assert answers["project_license"] == "no_license"


# @pytest.mark.parametrize("previous_db_filter", (".*", "custom"))
# def test_v4_0_0_migration(
#     tmp_path: Path,
#     cloned_template: Path,
#     supported_odoo_version: float,
#     previous_db_filter: str,
# ):
#     """Test migration to v4.0.0."""
#     target_filter = "^prod" if previous_db_filter == ".*" else previous_db_filter
#     migration_from_version, target = "v3.2.0", "v4.0.0"
#     # This part makes sense only when target version is not yet released
#     with local.cwd(cloned_template):
#         if target not in git("tag").split():
#             git("tag", "-d", "test")
#             git("tag", target)
#     with local.cwd(tmp_path):
#         # Copy previous version
#         copy(
#             src_path=str(cloned_template),
#             vcs_ref=migration_from_version,
#             force=True,
#             answers_file=".custom.copier-answers.yaml",
#             data={
#                 "odoo_version": supported_odoo_version,
#                 "odoo_dbfilter": previous_db_filter,
#                 "backup_dst": "file:///here",
#             },
#         )
#         git("config", "commit.gpgsign", "false")
#         git("add", ".")
#         git("commit", "-am", "reformat", retcode=1)
#         git("commit", "-am", f"copied from template in {migration_from_version}")
#         # Update to target version
#         copy(answers_file=".custom.copier-answers.yaml", vcs_ref=target, force=True)
#         git("add", ".")
#         git("commit", "-am", "reformat", retcode=1)
#         git("commit", "-am", f"updated from template in {target}")
#         # Assert correct answer
#         devel, test, prod = map(
#             lambda env: yaml.safe_load(docker_compose("-f", f"{env}.yaml", "config")),
#             ("devel", "test", "prod"),
#         )
#         assert "DB_FILTER" not in devel["services"]["odoo"]["environment"]
#         assert "DB_FILTER" not in test["services"]["odoo"]["environment"]
#         assert prod["services"]["odoo"]["environment"]["DB_FILTER"] == target_filter
#         assert (
#             prod["services"]["backup"]["environment"]["DBS_TO_INCLUDE"] == target_filter
#         )
#         answers = yaml.safe_load(Path(".custom.copier-answers.yaml").read_bytes())
#         assert answers["odoo_dbfilter"] == target_filter
