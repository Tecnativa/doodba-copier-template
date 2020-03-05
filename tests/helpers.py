import yaml
from plumbum import local
from plumbum.cmd import git

with open("copier.yml") as copier_fd:
    COPIER_SETTINGS = yaml.safe_load(copier_fd)

# Different tests test different Odoo versions
ALL_ODOO_VERSIONS = tuple(COPIER_SETTINGS["odoo_version"]["choices"])
CURRENT_ODOO_VERSIONS = tuple(v for v in ALL_ODOO_VERSIONS if v >= 8)


def clone_self_dirty(destination, tag="test", source="."):
    """Clone this repo to a temporary destination including dirty changes.

    The clone will have a 'test' tag (or any value you give) in its HEAD.
    """
    patch = git("diff")
    git("clone", source, destination)
    with local.cwd(destination):
        if patch:
            (git["apply", "--reject"] << patch)()
            git("add", source)
            git(
                "commit",
                "--author=Test<test@test>",
                "--message=dirty changes",
                "--no-verify",
            )
        git("tag", "--force", tag)
