"""Tests for the optional OdooClaw integration (use_odooclaw)."""

import json
import os
import shutil
from pathlib import Path

import pytest
import yaml
from copier import run_copy
from plumbum import ProcessExecutionError, local
from plumbum.cmd import docker, git

# Versions where the use_odooclaw question is available (copier.yml `when`).
ODOOCLAW_ODOO_VERSIONS = (16.0, 17.0, 18.0)


def _render(cloned_template, tmp_path, **data):
    project = tmp_path / "project"
    run_copy(
        src_path=str(cloned_template),
        dst_path=str(project),
        data=data,
        vcs_ref="HEAD",
        defaults=True,
        overwrite=True,
        unsafe=True,
    )
    return project


class TestOdooclawDisabled:
    @pytest.fixture(scope="class")
    def project(self, request, tmp_path_factory):
        return _render(
            request.getfixturevalue("cloned_template"),
            tmp_path_factory.mktemp("off"),
            odoo_version=18.0,
            use_odooclaw=False,
        )

    def test_no_generated_files(self, project: Path):
        for rel in (
            ".docker/odooclaw.env",
            "odooclaw/config/config.json",
            "odooclaw/.gitignore",
            "scripts/setup-odooclaw.sh",
            "scripts/smoke-test-odooclaw.sh",
        ):
            assert not (project / rel).exists(), f"{rel} must not be generated"
        assert not (project / "odooclaw").exists()
        # The conditional path template must not leak anything anywhere.
        assert "OdooClaw gateway" not in (project / ".gitignore").read_text()
        stray = [
            str(path.relative_to(project))
            for path in project.rglob("*")
            if "{%" in path.name or "%}" in path.name
        ]
        assert not stray, f"unrendered paths generated: {stray}"

    def test_no_services_in_compose(self, project: Path):
        for compose in ("devel.yaml", "prod.yaml"):
            data = yaml.safe_load((project / compose).read_text())
            assert "odooclaw" not in data["services"]
            assert "redis" not in data["services"]
            assert "odooclaw_data" not in data.get("volumes", {})

    def test_no_repo_entries(self, project: Path):
        repos = (project / "odoo/custom/src/repos.yaml").read_text()
        addons = (project / "odoo/custom/src/addons.yaml").read_text()
        assert "odoo-addons" not in repos
        assert "odooclaw" not in addons


class TestOdooclawEnabled:
    @pytest.fixture(scope="class")
    def project(self, request, tmp_path_factory):
        return _render(
            request.getfixturevalue("cloned_template"),
            tmp_path_factory.mktemp("on"),
            odoo_version=18.0,
            use_odooclaw=True,
            odooclaw_provider="openai",
            odooclaw_model="gpt-4o-mini",
        )

    def test_generated_files(self, project: Path):
        for rel in (
            ".docker/odooclaw.env",
            "odooclaw/config/config.json",
            "scripts/setup-odooclaw.sh",
            "scripts/smoke-test-odooclaw.sh",
        ):
            assert (project / rel).is_file(), f"{rel} must be generated"

    def test_config_is_valid_json_without_placeholders(self, project: Path):
        raw = (project / "odooclaw/config/config.json").read_text()
        config = json.loads(raw)
        assert "${" not in raw
        assert config["agents"]["defaults"]["provider"] == "openai"
        assert config["agents"]["defaults"]["model"] == "gpt-4o-mini"
        assert config["channels"]["odoo"]["webhook_port"] == 18790
        assert config["tools"]["mcp"]["servers"]["odoo-mcp"]["enabled"] is True

    def test_env_file(self, project: Path):
        env = (project / ".docker/odooclaw.env").read_text()
        assert "ODOOCLAW_CHANNELS_ODOO_WEBHOOK_PORT=18790" in env
        assert "ODOOCLAW_JOB_STORE=odoo" in env
        # DB is NOT pinned in the shared env file (it is per-compose-file).
        assert "ODOO_DB=" not in env
        # compose resolves ${...} in an env_file from the shell / project .env,
        # never from the file itself: a reference here would silently be empty.
        assignments = [
            line
            for line in env.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert not [line for line in assignments if "${" in line], (
            "env_file values must be literal, not ${...}"
        )
        assert any(
            line.startswith("ODOO_PASSWORD=") for line in assignments
        )  # credentials are filled in by hand here

    def test_services_in_compose(self, project: Path):
        for compose, expected_db in (("devel.yaml", "devel"), ("prod.yaml", "prod")):
            data = yaml.safe_load((project / compose).read_text())
            svc = data["services"]["odooclaw"]
            assert svc["build"]["context"] == "./odooclaw"
            assert svc["build"]["dockerfile"] == "docker/Dockerfile"
            assert svc["environment"]["ODOO_DB"] == expected_db
            assert svc["environment"]["ODOOCLAW_CHANNELS_ODOO_TARGET_DB"] == expected_db
            assert "redis" in data["services"]
            assert "odooclaw_data" in data["volumes"]

    def test_repo_and_addons_entries(self, project: Path):
        repos = (project / "odoo/custom/src/repos.yaml").read_text()
        assert "nicolasramos/odoo-addons.git" in repos
        assert "target: odooclaw $ODOO_VERSION" in repos
        addons = yaml.safe_load((project / "odoo/custom/src/addons.yaml").read_text())
        assert "mail_bot_odooclaw" in addons["odoo-addons"]
        assert "mail_bot_odooclaw_account" in addons["odoo-addons"]

    def test_gateway_is_reachable_from_the_host(self, project: Path):
        """A published port is useless if the gateway binds to loopback.

        The gateway's HTTP server listens on $ODOOCLAW_GATEWAY_HOST, whose
        built-in default is 127.0.0.1. Without overriding it the published port
        never reaches the process and the shipped smoke test fails.
        """
        env = (project / ".docker/odooclaw.env").read_text()
        assert "ODOOCLAW_GATEWAY_HOST=0.0.0.0" in env

    def test_gateway_has_egress(self, project: Path):
        """The default network is internal (no internet).

        The gateway has to reach the configured LLM provider, so it must also
        join the public network — the same one the proxy uses.
        """
        for compose in ("devel.yaml", "prod.yaml"):
            data = yaml.safe_load((project / compose).read_text())
            networks = data["services"]["odooclaw"].get("networks") or {}
            assert networks, (
                f"{compose}: the odooclaw service declares no networks, so it "
                "falls back to the internal (no-egress) default network"
            )

    def test_no_unrendered_jinja(self, project: Path):
        for path in project.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            # .j2 files are runtime templates (OCA readme generator), not
            # copier leftovers.
            if path.suffix == ".j2":
                continue
            try:
                content = path.read_text()
            except (UnicodeDecodeError, PermissionError):
                continue
            assert "{%" not in content, f"unrendered jinja in {path}"
            assert "{{ " not in content, f"unrendered jinja in {path}"

    def test_compose_config_valid(self, project: Path):
        with local.cwd(project):
            for compose in ("devel.yaml", "prod.yaml"):
                docker(
                    "compose",
                    "-f",
                    "common.yaml",
                    "-f",
                    compose,
                    "config",
                    "-q",
                )


class TestOdooclawVersions:
    """The module list and question availability per Odoo version."""

    @pytest.mark.parametrize("odoo_version", ODOOCLAW_ODOO_VERSIONS)
    def test_module_list_per_version(self, cloned_template, tmp_path, odoo_version):
        project = _render(
            cloned_template,
            tmp_path / f"v{odoo_version}",
            odoo_version=odoo_version,
            use_odooclaw=True,
            odooclaw_provider="openai",
            odooclaw_model="gpt-4o-mini",
        )
        addons = yaml.safe_load((project / "odoo/custom/src/addons.yaml").read_text())
        modules = addons["odoo-addons"]
        assert "mail_bot_odooclaw" in modules
        if odoo_version >= 18.0:
            assert "mail_bot_odooclaw_account" in modules
            assert "mail_bot_odooclaw_crm" in modules
        else:
            assert modules == ["mail_bot_odooclaw"]
        # Compose still valid on every supported version
        with local.cwd(project):
            docker("compose", "-f", "common.yaml", "-f", "devel.yaml", "config", "-q")

    def test_not_applied_outside_the_supported_versions(
        self, cloned_template, tmp_path
    ):
        """Outside 16-18 OdooClaw must not be applied, even if forced."""
        # copier.yml hides the question, so a normal render never sets it. This
        # simulates the other way in: an answers file carried over from a project
        # generated on a supported version and later updated to an unsupported
        # one. The answer must not half-apply — leaving the compose services
        # pointing at a build context that is no longer generated — so every
        # piece has to agree.
        project = _render(
            cloned_template,
            tmp_path / "unsupported",
            odoo_version=19.0,
            use_odooclaw=True,
        )
        devel = (project / "devel.yaml").read_text()
        prod = (project / "prod.yaml").read_text()
        addons = (project / "odoo/custom/src/addons.yaml").read_text()
        repos = (project / "odoo/custom/src/repos.yaml").read_text()
        assert "odooclaw" not in devel
        assert "odooclaw" not in prod
        assert "mail_bot_odooclaw" not in addons
        assert "odoo-addons" not in repos
        assert not (project / "odooclaw").exists()


class TestOdooclawBootstrap:
    """`scripts/setup-odooclaw.sh` must really produce compose's build context.

    The compose service builds with `context: ./odooclaw` +
    `dockerfile: docker/Dockerfile`, and the project already ships
    `odooclaw/config/config.json`, so the script cannot simply `git clone` the
    repository into `odooclaw/`. These tests run it for real (it clones the
    gateway from GitHub) and check what the build context ends up looking like.
    """

    @pytest.fixture(scope="class")
    def project(self, request, tmp_path_factory):
        return _render(
            request.getfixturevalue("cloned_template"),
            tmp_path_factory.mktemp("boot"),
            odoo_version=18.0,
            use_odooclaw=True,
            odooclaw_provider="openai",
            odooclaw_model="gpt-4o-mini",
        )

    @pytest.fixture(scope="class")
    def bootstrapped(self, project: Path):
        with local.cwd(project):
            local["bash"]("scripts/setup-odooclaw.sh")
        return project

    def test_build_context_is_produced(self, bootstrapped: Path):
        """The exact path compose asks for must exist after the script."""
        assert (bootstrapped / "odooclaw" / "docker" / "Dockerfile").is_file()
        assert (bootstrapped / "odooclaw" / "go.mod").is_file()

    def test_compose_build_paths_exist(self, bootstrapped: Path):
        """`docker compose config` does not check the Dockerfile path: do it."""
        for compose in ("devel.yaml", "prod.yaml"):
            build = yaml.safe_load((bootstrapped / compose).read_text())["services"][
                "odooclaw"
            ]["build"]
            dockerfile = bootstrapped / build["context"] / build["dockerfile"]
            assert dockerfile.is_file(), f"{compose}: {dockerfile} does not exist"

    def test_generated_config_is_preserved(self, bootstrapped: Path):
        """The gateway source must not overwrite the rendered config.json."""
        raw = (bootstrapped / "odooclaw" / "config" / "config.json").read_text()
        config = json.loads(raw)
        assert config["agents"]["defaults"]["provider"] == "openai"
        assert config["agents"]["defaults"]["model"] == "gpt-4o-mini"
        assert "${" not in raw

    def test_rerun_is_idempotent(self, bootstrapped: Path):
        with local.cwd(bootstrapped):
            output = local["bash"]("scripts/setup-odooclaw.sh")
        assert "already present" in output

    def test_gateway_source_is_git_ignored(self, bootstrapped: Path, tmp_path):
        """Third-party source must not be committable; config.json must be."""
        repo = tmp_path / "ignore-check"
        (repo / "odooclaw" / "docker").mkdir(parents=True)
        (repo / "odooclaw" / "config").mkdir(parents=True)
        shutil.copy(
            bootstrapped / "odooclaw" / ".gitignore", repo / "odooclaw" / ".gitignore"
        )
        (repo / "odooclaw" / "docker" / "Dockerfile").write_text("FROM scratch\n")
        (repo / "odooclaw" / "config" / "config.json").write_text("{}\n")
        # The gateway's own example config arrives with the rsync; only the
        # generated config.json may be committed.
        (repo / "odooclaw" / "config" / "config.example.json").write_text("{}\n")
        with local.cwd(repo):
            git("init", "--quiet")
            # exit 0 => ignored (a raise would fail the test)
            git("check-ignore", "--quiet", "odooclaw/docker/Dockerfile")
            git("check-ignore", "--quiet", "odooclaw/config/config.example.json")
            with pytest.raises(ProcessExecutionError):
                git("check-ignore", "--quiet", "odooclaw/config/config.json")

    def test_disable_after_bootstrap(self, bootstrapped: Path, tmp_path):
        """Deactivating after a real bootstrap must not leave the third-party
        gateway source committable.

        Copier applies its own deletions *after* `after-update` runs, so an
        ignore file written back for a surviving `odooclaw/` tree would be
        wiped with the update: the task removes the whole tree instead (it is
        re-fetchable with scripts/setup-odooclaw.sh on the next enable).
        """
        project = tmp_path / "disabled"
        shutil.copytree(bootstrapped, project)

        answers = project / ".copier-answers.yml"
        flipped = answers.read_text().replace(
            "use_odooclaw: true", "use_odooclaw: false"
        )
        assert "use_odooclaw: false" in flipped
        answers.write_text(flipped)

        with local.cwd(project):
            local["invoke"]("after-update")

        # Generated pieces and the fetched tree are gone ...
        assert not (project / "scripts" / "setup-odooclaw.sh").exists()
        assert not (project / "scripts" / "smoke-test-odooclaw.sh").exists()
        assert not (project / "odooclaw").exists()
        # ... so there is no third-party file left to stage ...
        if not (project / ".git").is_dir():
            git("init", "--quiet", str(project))
        with local.cwd(project):
            status = git("status", "--porcelain", "--", "odooclaw")
        assert status.strip() == ""
        # ... and the managed blocks are back to the pristine state.
        addons = project / "odoo" / "custom" / "src" / "addons.yaml"
        repos = project / "odoo" / "custom" / "src" / "repos.yaml"
        assert addons.read_bytes() == b""  # pristine addons.yaml is empty
        assert "# BEGIN odooclaw" not in repos.read_text()

    def test_disable_via_real_copier_update(
        self, bootstrapped: Path, cloned_template, tmp_path_factory
    ):
        """A real ``copier update`` to false must leave the repo committable.

        ``test_disable_after_bootstrap`` runs the task by hand and therefore
        never exercises copier's own merge, which is where two real problems
        show up: an unresolved conflict in README.md (``git commit`` then
        refuses to run) and the gateway's own ``config.example.json`` coming
        back because it is tracked while the template never managed it.
        """
        project = tmp_path_factory.mktemp("cycle") / "project"
        shutil.copytree(bootstrapped, project)

        # Reference: the same answers with the option off, rendered fresh.
        off = _render(
            cloned_template,
            tmp_path_factory.mktemp("off"),
            odoo_version=18.0,
            use_odooclaw=False,
            odooclaw_provider="openai",
            odooclaw_model="gpt-4o-mini",
        )

        answers = yaml.safe_load((project / ".copier-answers.yml").read_text())
        # copier checks out the recorded commit while updating; if the source
        # cannot resolve it, the failure below would be cryptic.
        git(
            "-C",
            str(cloned_template),
            "cat-file",
            "-e",
            f"{answers['_commit']}^{{commit}}",
        )

        if not (project / ".git").is_dir():
            git("init", "--quiet", str(project))
        with local.cwd(project):
            # The project's own pre-commit hooks (prettier) rewrite files on
            # the first commit; keep staging until git takes it.
            for _ in range(4):
                git("add", "--all")
                if not git("status", "--porcelain").strip():
                    break  # already committed
                try:
                    git(
                        "-c",
                        "user.email=ci@example.com",
                        "-c",
                        "user.name=ci",
                        "commit",
                        "--quiet",
                        "-m",
                        "bootstrapped",
                    )
                    break
                except ProcessExecutionError:
                    continue  # hooks modified files; stage them and retry
            else:
                raise AssertionError("could not commit the bootstrapped project")
            assert not git("status", "--porcelain").strip()
            # What a user gets for `git add -A` after the bootstrap: the
            # gateway's own example config must not be committable.
            assert (
                git("ls-files", "--", "odooclaw/config/config.example.json").strip()
                == ""
            )
            readme_before = (project / "README.md").read_bytes()

            local["copier"](
                "update",
                "--trust",
                "--defaults",
                "--vcs-ref",
                "HEAD",
                "-d",
                "use_odooclaw=false",
            )

        # 1. No unresolved conflict: the repository must still be committable.
        with local.cwd(project):
            assert git("ls-files", "-u").strip() == ""
            status = git("status", "--porcelain")
        conflicts = [
            line
            for line in status.splitlines()
            if line[:2] in {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}
        ]
        assert not conflicts, conflicts
        assert "use_odooclaw: false" in (project / ".copier-answers.yml").read_text()

        # 2. The update must not rewrite the README at all.
        assert (project / "README.md").read_bytes() == readme_before
        assert b"OdooClaw" not in readme_before  # section left the template

        # 3. The third-party tree is gone, and nothing under it is committable.
        gateway = project / "odooclaw"
        if gateway.exists():
            leftovers = [
                str(path.relative_to(project))
                for path in gateway.rglob("*")
                if path.is_file()
            ]
            assert leftovers == [], leftovers
        assert not (project / ".docker" / "odooclaw.env").exists()
        assert not (project / "scripts" / "setup-odooclaw.sh").exists()

        # 4. What the option controls is byte-identical to a render with it off.
        for rel in (
            "README.md",
            "odoo/custom/src/addons.yaml",
            "odoo/custom/src/repos.yaml",
        ):
            assert (project / rel).read_bytes() == (off / rel).read_bytes(), rel

        # 5. And the repo really accepts a commit afterwards (git refuses when
        #    the index has unmerged entries, hooks aside).
        with local.cwd(project):
            git("add", "--all")
            assert git("ls-files", "--", "odooclaw").strip() == ""
            git(
                "-c",
                "user.email=ci@example.com",
                "-c",
                "user.name=ci",
                "commit",
                "--quiet",
                "--no-verify",
                "--allow-empty",
                "-m",
                "odoo disabled",
            )

    @pytest.mark.skipif(
        not os.environ.get("ODOOCLAW_BUILD_TESTS"),
        reason="set ODOOCLAW_BUILD_TESTS=1 to run the real (network+disk heavy) build",
    )
    def test_docker_compose_build(self, bootstrapped: Path):
        """The acceptance criterion: the image really builds from source.

        The gateway's Dockerfile installs the NVIDIA CUDA stack through
        ``openai-whisper`` (~8 GB), and the snapshotter needs a second copy of
        that layer while committing it: a docker disk under ~25 GB cannot hold
        it. That is an environment limit, not a defect in this branch, so it
        skips explicitly instead of reporting a false failure; anything else
        (bad context path, compile error) still fails the test.
        """
        with local.cwd(bootstrapped):
            try:
                docker(
                    "compose",
                    "-f",
                    "common.yaml",
                    "-f",
                    "devel.yaml",
                    "build",
                    "odooclaw",
                )
            except ProcessExecutionError as exc:
                # [Errno 28] during the gateway's own pip layer (it installs
                # the NVIDIA CUDA stack through openai-whisper).
                output = f"{exc.stdout}\n{exc.stderr}\n{exc}".lower()
                if "no space left on device" in output or "errno 28" in output:
                    pytest.skip(
                        "docker disk full while committing the gateway's ~8 GB "
                        "pip layer; re-run on a docker disk >= 25 GB"
                    )
                raise
