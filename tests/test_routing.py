import time
import uuid
from pathlib import Path

import pytest
import requests
from copier import run_copy
from packaging import version
from plumbum import local
from python_on_whales import DockerClient

from .conftest import DBVER_PER_ODOO


@pytest.mark.parametrize("environment", ("test", "prod"))
def test_multiple_domains(
    cloned_template: Path,
    supported_odoo_version: float,
    tmp_path: Path,
    traefik_host: dict,
    environment: str,
):
    """Test multiple domains are produced properly."""
    base_domain = traefik_host["hostname"]
    base_path = f"{base_domain}/web/login"
    # XXX Remove traefik1 specific stuff some day
    is_traefik1 = version.parse(traefik_host["traefik_version"]) < version.parse("2")
    is_traefik3 = version.parse(traefik_host["traefik_version"]) >= version.parse("3")
    data = {
        "odoo_listdb": True,
        "traefik_version": int(
            str(version.parse(traefik_host["traefik_version"])).split(".")[0]
        ),
        "odoo_version": supported_odoo_version,
        "postgres_version": DBVER_PER_ODOO[supported_odoo_version]["latest"],
        "paths_without_crawlers": ["/web/login", "/web/database"],
        "project_name": uuid.uuid4().hex,
        f"domains_{environment}": [
            # main0 has no TLS
            {"hosts": [f"main0.{base_domain}"], "cert_resolver": False},
            {
                "hosts": [f"alt0.main0.{base_domain}", f"alt1.main0.{base_domain}"],
                "cert_resolver": None,
                "redirect_to": f"main0.{base_domain}",
            },
            # main1 has self-signed certificates
            {"hosts": [f"main1.{base_domain}"], "cert_resolver": True},
            {
                "hosts": [f"alt0.main1.{base_domain}", f"alt1.main1.{base_domain}"],
                "cert_resolver": True,
                "redirect_to": f"main1.{base_domain}",
                "redirect_permanent": True,
            },
            # main2 only serves certain routes
            {
                "hosts": [f"main2.{base_domain}"],
                "path_prefixes": ["/insecure/"],
                "entrypoints": ["web-insecure"],
                "cert_resolver": False,
            },
            # main3 only serves certain routes in web-alt entrypoint
            {
                "hosts": [f"main3.{base_domain}"],
                "path_prefixes": ["/alt/"],
                "entrypoints": ["web-alt"],
                "cert_resolver": False,
            },
        ],
    }
    if supported_odoo_version < 16:
        data["postgres_version"] = 13
    dc = DockerClient(compose_files=[f"{environment}.yaml"])
    with local.cwd(tmp_path):
        run_copy(
            src_path=str(cloned_template),
            dst_path=".",
            data=data,
            vcs_ref="test",
            defaults=True,
            overwrite=True,
            unsafe=True,
        )
        # Check if Odoo options were passed correctly
        docker_compose_config = dc.compose.config()
        assert docker_compose_config.services["odoo"].environment["LIST_DB"] == "true"
        try:
            dc.compose.build()
            dc.compose.run(
                "odoo",
                command=["--stop-after-init", "-i", "base"],
                remove=True,
            )
            dc.compose.up(detach=True)
            time.sleep(10)
            # XXX Remove all Traefik 1 tests once it disappears
            if is_traefik1:
                # main0, globally redirected to TLS
                response = requests.get(f"http://main0.{base_path}", verify=False)
                assert response.ok
                assert response.url == f"https://main0.{base_domain}:443/web/login"
                assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
                # alt0 and alt1, globally redirected to TLS
                for alt_num in range(2):
                    response = requests.get(
                        f"http://alt{alt_num}.main0.{base_path}", verify=False
                    )
                    assert response.ok
                    assert response.url == f"https://main0.{base_path}"
                    assert response.history[0].status_code == 302
                # main2 serves https on port 80; returns a 404 from Traefik (not from
                # Odoo) with global HTTPS redirection
                bad_response = requests.get(
                    f"http://main2.{base_domain}/insecure/path",
                    verify=False,
                )
                assert not bad_response.ok
                assert bad_response.status_code == 404
                assert "Server" not in bad_response.headers  # 404 comes from Traefik
                assert (
                    bad_response.url == f"https://main2.{base_domain}:443/insecure/path"
                )
            else:
                # main0, no TLS
                if not is_traefik3:
                    response = requests.get(f"http://main0.{base_path}")
                    assert response.ok
                    assert response.url == f"http://main0.{base_path}"
                    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
                    # alt0 and alt1, no TLS
                    for alt_num in range(2):
                        response = requests.get(
                            f"http://alt{alt_num}.main0.{base_path}"
                        )
                        assert response.ok
                        assert response.url == f"http://main0.{base_path}"
                        assert response.history[0].status_code == 302
                # main2 serves https on port 80; returns a 404 from Odoo (not from
                # Traefik) without HTTPS redirection
                bad_response = requests.get(
                    f"http://main2.{base_domain}/insecure/path",
                    verify=False,
                )
                assert not bad_response.ok
                assert bad_response.status_code == 404
                assert "Werkzeug" in bad_response.headers.get("Server")
                assert bad_response.url == f"http://main2.{base_domain}/insecure/path"
            # main3 cannot find /web on port 8080; no HTTPS redirection
            bad_response = requests.get(
                f"http://main3.{base_domain}:8080/web",
            )
            assert not bad_response.ok
            assert bad_response.status_code == 404
            assert "Server" not in bad_response.headers  # 404 comes from Traefik
            assert bad_response.url == f"http://main3.{base_domain}:8080/web"
            # main3 will route to odoo in /alt/foo but fail with 404 from there, no HTTPS
            bad_response = requests.get(
                f"http://main3.{base_domain}:8080/alt/foo",
            )
            assert not bad_response.ok
            assert bad_response.status_code == 404
            assert "Werkzeug" in bad_response.headers.get("Server")
            assert bad_response.url == f"http://main3.{base_domain}:8080/alt/foo"
            # main1, with self-signed TLS
            response = requests.get(f"http://main1.{base_path}", verify=False)
            assert response.ok
            assert response.url == (
                f"https://main1.{base_domain}:443/web/login"
                if is_traefik1
                else f"https://main1.{base_path}"
            )
            if not is_traefik3:
                assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
                # alt0 and alt1, with self-signed TLS
                for alt_num in range(2):
                    response = requests.get(
                        f"http://alt{alt_num}.main1.{base_domain}/web/database/selector",
                        verify=False,
                    )
                    assert response.ok
                    assert (
                        response.url
                        == f"https://main1.{base_domain}/web/database/selector"
                    )
                    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
                    # Search for a response in the chain with the 301 return code
                    # as several will be made during the redirection
                    assert filter(lambda r: r.status_code == 301, response.history)
            # missing, which fails with Traefik 404, both with and without TLS
            bad_response = requests.get(
                f"http://missing.{base_path}", verify=not is_traefik1
            )
            assert bad_response.status_code == 404
            assert "Server" not in bad_response.headers
            bad_response = requests.get(f"https://missing.{base_path}", verify=False)
            assert bad_response.status_code == 404
            assert "Server" not in bad_response.headers
        finally:
            dc.compose.down(remove_images="local", remove_orphans=True)
