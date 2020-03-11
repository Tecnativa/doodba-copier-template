import pytest
import yaml
from copier.main import copy

from .helpers import ALL_ODOO_VERSIONS, clone_self_dirty


@pytest.mark.parametrize("odoo_version", ALL_ODOO_VERSIONS)
def test_prod_alt_domains(tmpdir, odoo_version):
    """Test prod alt domains are produced properly."""
    src, dst = tmpdir / "src", tmpdir / "dst"
    clone_self_dirty(src)
    copy(
        src_path=str(src),
        dst_path=str(dst),
        vcs_ref="test",
        force=True,
        data={
            "odoo_version": odoo_version,
            "domain_prod": "main.example.com",
            "domain_prod_alternatives": ["alt0.example.com", "alt1.example.com"],
        },
    )
    prod = yaml.safe_load((dst / "prod.yaml").read())
    assert (
        "${DOMAIN_PROD}"
        in prod["services"]["odoo"]["labels"]["traefik.longpolling.frontend.rule"]
    )
    assert (
        "${DOMAIN_PROD}"
        in prod["services"]["odoo"]["labels"]["traefik.www.frontend.rule"]
    )
    assert (
        "${DOMAIN_PROD_ALT_0}"
        in prod["services"]["odoo"]["labels"]["traefik.alt-0.frontend.redirect.regex"]
    )
    assert (
        "${DOMAIN_PROD}"
        in prod["services"]["odoo"]["labels"][
            "traefik.alt-0.frontend.redirect.replacement"
        ]
    )
    assert (
        "${DOMAIN_PROD_ALT_1}"
        in prod["services"]["odoo"]["labels"]["traefik.alt-1.frontend.rule"]
    )
    assert (
        "${DOMAIN_PROD_ALT_1}"
        in prod["services"]["odoo"]["labels"]["traefik.alt-1.frontend.redirect.regex"]
    )
    assert (
        "${DOMAIN_PROD}"
        in prod["services"]["odoo"]["labels"][
            "traefik.alt-1.frontend.redirect.replacement"
        ]
    )
    assert (
        "${DOMAIN_PROD_ALT_1}"
        in prod["services"]["odoo"]["labels"]["traefik.alt-1.frontend.rule"]
    )
