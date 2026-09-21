from plumbum import local
from plumbum.cmd import invoke


def test_pre_commit_in_template(request):
    """Make sure linters are happy."""
    with local.cwd(request.config.rootpath):
        invoke("lint")
