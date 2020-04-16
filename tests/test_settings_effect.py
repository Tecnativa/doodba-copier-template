from pathlib import Path

import yaml
from copier.main import copy


def test_prod_alt_domains(
    tmp_path: Path, any_odoo_version: float, cloned_template: Path
):
    """Test prod alt domains are produced properly."""
    copy(
        src_path=str(cloned_template),
        dst_path=str(tmp_path),
        vcs_ref="test",
        force=True,
        data={
            "odoo_version": any_odoo_version,
            "domain_prod": "main.example.com",
            "domain_prod_alternatives": ["alt0.example.com", "alt1.example.com"],
        },
    )
    prod = yaml.safe_load((tmp_path / "prod.yaml").read_text())
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
