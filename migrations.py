"""Template migration scripts.

This file is executed through invoke by copier when updating child projects.
"""

import shutil
from pathlib import Path

from invoke import task
from invoke.util import yaml


@task
def from_doodba_scaffolding_to_copier(c):
    print("Removing remaining garbage from doodba-scaffolding.")
    shutil.rmtree(Path(".vscode", "doodba"), ignore_errors=True)
    garbage = (
        Path(".travis.yml"),
        Path(".vscode", "doodbasetup.py"),
        Path("odoo", "custom", "src", "private", ".empty"),
    )
    for path in garbage:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    # When using Copier >= 3.0.5, this file didn't get properly migrated
    editorconfig_file = Path(".editorconfig")
    editorconfig_contents = editorconfig_file.read_text()
    editorconfig_contents = editorconfig_contents.replace(
        "[*.yml]", "[*.{code-snippets,code-workspace,json,md,yaml,yml}{,.jinja}]", 1
    )
    editorconfig_file.write_text(editorconfig_contents)


@task
def remove_odoo_auto_folder(c):
    """This folder makes no more sense for us.

    The `invoke develop` task now handles its creation, which is done with
    host user UID and GID to avoid problems.

    There's no need to have it in our code tree anymore.
    """
    shutil.rmtree(Path("odoo", "auto"), ignore_errors=True)


@task
def remove_vscode_launch_and_tasks(c, dst_path):
    """Remove .vscode/{launch,tasks}.json file.

    Launch configurations are now generated in the doodba.*.code-workspace file.
    """
    for fname in ("launch", "tasks"):
        garbage = Path(dst_path, ".vscode", f"{fname}.json")
        if garbage.is_file():
            garbage.unlink()


@task
def remove_vscode_settings(c, dst_path):
    """Remove .vscode/{launch,tasks}.json file.

    Launch configurations are now generated in the doodba.*.code-workspace file.
    """
    garbage = Path(dst_path, ".vscode", "settings.json")
    if garbage.is_file():
        garbage.unlink()


@task
def update_domains_structure(c, dst_path, answers_rel_path):
    """Migrates from v1 to v2 domain structure.

    In template v1:

    - domain_prod was a str
    - domain_prod_alternatives was a list of str
    - domain_test was a str

    In template v2, we support multiple domains:

    - domains_prod is a list of dicts
    - domains_test is a list of dicts
    """
    answers_path = Path(dst_path, answers_rel_path)
    answers_yaml = yaml.safe_load(answers_path)
    # Update domains_prod
    domain_prod = answers_yaml.pop("domain_prod", None)
    domain_prod_alternatives = answers_yaml.pop("domain_prod_alternatives", None)
    new_domains_prod = []
    if domain_prod:
        new_domains_prod.append(
            {"hosts": [domain_prod], "cert_resolver": "letsencrypt"}
        )
        if domain_prod_alternatives:
            new_domains_prod.append(
                {
                    "hosts": domain_prod_alternatives,
                    "cert_resolver": "letsencrypt",
                    "redirect_to": domain_prod,
                }
            )
    answers_yaml.setdefault("domains_prod", new_domains_prod)
    # Update domains_test
    domain_test = answers_yaml.pop("domain_test", None)
    new_domains_test = []
    if domain_test:
        new_domains_test.append(
            {"hosts": [domain_test], "cert_resolver": "letsencrypt"}
        )
    answers_yaml.setdefault("domains_test", new_domains_test)
    answers_path.write_text(yaml.safe_dump(answers_yaml))
    # Remove .env file
    Path(dst_path, ".env").unlink()


@task
def update_no_license(c, dst_path, answers_rel_path):
    """Update projects with no license.

    In template version < 3.0.0, no license was `None`. In 3.0.0 it was changed
    to `""`, to make it compatible with Copier 6, but that made it not work
    fine with Copier 5. So, in version 3.0.1 it was changed to `"no_license"`.
    This value will always be a string, no matter the parser, and should make
    the parameter work fine in any Copier version.

    This migrates old answers to this new format.
    """
    answers_path = Path(dst_path, answers_rel_path)
    answers_yaml = yaml.safe_load(answers_path)
    if (
        not answers_yaml.get("project_license")
        or answers_yaml.get("project_license") == "no_license"
    ):
        answers_yaml["project_license"] = "no_license"
        answers_path.write_text(yaml.safe_dump(answers_yaml))
        # Delete LICENSE if it existed but was empty
        license = Path(dst_path, "LICENSE")
        try:
            if not license.read_text().strip():
                license.unlink()
        except FileNotFoundError:
            pass  # LICENSE does not exist, and that's good


@task
def db_filter_prefix_default(c, dst_path, answers_rel_path):
    """Update projects with default DB filter including main DB prefix.

    In template version < 4.0.0, the default value for odoo_dbfilter was ".*"
    always. Starting with 4.0.0, the default value will be applied only to
    production environments and will include the main DB name as a prefix.

    Update answers for projects that didn't change the default.
    """
    answers_path = Path(dst_path, answers_rel_path)
    answers_yaml = yaml.safe_load(answers_path)
    postgres_dbname = answers_yaml.get("postgres_dbname")
    if answers_yaml.get("odoo_dbfilter") == ".*" and postgres_dbname:
        # Replace odoo_dbfilter value in answers file
        answers_path.write_text(
            answers_path.read_text().replace(
                "odoo_dbfilter: .*", f"odoo_dbfilter: ^{postgres_dbname}"
            )
        )
        common_path = Path(dst_path, "common.yaml")
        common_path.write_text(
            common_path.read_text().replace(
                'DBS_TO_INCLUDE: ".*"', f'DBS_TO_INCLUDE: "^{postgres_dbname}"'
            )
        )
        prod_path = Path(dst_path, "prod.yaml")
        prod_path.write_text(
            prod_path.read_text().replace(
                'DB_FILTER: ".*"', f'DB_FILTER: "^{postgres_dbname}"'
            )
        )


def get_old_proxy_data(compose_file_path):
    data = yaml.safe_load(compose_file_path)
    services = data.get("services", {})
    domains = set()
    containers = set()
    for service_name, service in services.items():
        image = service.get("image", "")
        if "tecnativa/docker-whitelist" not in image:
            continue
        containers.add(service_name)
        networks = service.get("networks", {})
        for net_conf in networks.values():
            if not net_conf:
                continue
            aliases = net_conf.get("aliases", [])
            for alias in aliases:
                domains.add(alias)
    return domains, containers


def _add_new_items_to_list(dst_path, answers_rel_path, varname, items):
    answers_path = Path(dst_path, answers_rel_path)
    answers_yaml = yaml.safe_load(answers_path)
    if varname not in answers_yaml:
        answers_yaml[varname] = []
    for item in items:
        if item not in answers_yaml[varname]:
            answers_yaml[varname].append(item)
    answers_path.write_text(yaml.safe_dump(answers_yaml))


@task
def migrate_to_new_proxy(c, dst_path, answers_rel_path):
    devel_compose = Path(dst_path, "devel.yaml")
    test_compose = Path(dst_path, "test.yaml")
    test_domains, test_containers = get_old_proxy_data(test_compose)
    devel_domains, devel_containers = get_old_proxy_data(devel_compose)
    _add_new_items_to_list(
        dst_path, answers_rel_path, "whitelisted_hosts_test", test_domains
    )
    _add_new_items_to_list(
        dst_path, answers_rel_path, "whitelisted_hosts_devel", devel_domains
    )
    devel_data = yaml.safe_load(devel_compose)
    test_data = yaml.safe_load(test_compose)
    devel_data["services"]["odoo"]["depends_on"] = [
        item
        for item in devel_data["services"]["odoo"]["depends_on"]
        if item not in devel_containers
    ]
    test_data["services"]["odoo"]["depends_on"] = [
        item
        for item in test_data["services"]["odoo"]["depends_on"]
        if item not in test_containers
    ]
    devel_compose.write_text(yaml.safe_dump(devel_data))
    test_compose.write_text(yaml.safe_dump(test_data))


@task
def add_new_domains(
    c, dst_path, answers_rel_path, version, varname="whitelisted_hosts_test"
):
    # We need to keep a list of new domains added per version to add them in upgrades
    # TODO: Maybe fix this in copier
    domains_version = {
        "9.6.0": [
            "accounts.google.com",
            "api.openrouteservice.org",
            "api.unsplash.com",
            "apis.google.com",
            "cdnjs.cloudflare.com",
            "download.geonames.org",
            "ec.europa.eu",
            "fonts.cdnfonts.com",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
            "images.unsplash.com",
            "iap-services.odoo.com",
            "maps.googleapis.com",
            "media-api.odoo.com",
            "olg.api.odoo.com",
            "www.google.com",
            "www.googleapis.com",
            "www.gravatar.com",
            "undraw.co",
            "updates.maxmind.com",
            "www.ecb.europa.eu",
            "www.xe.com",
            "sis-t.redsys.es",
            "prewww1.aeat.es",
            "www2.agenciatributaria.gob.es",
            "www.openstreetmap.org",
            "nominatim.openstreetmap.org",
            "www.bizkaia.eus",
            "sii.araba.eus",
            "vies.api.odoo.com",
        ]
    }
    _add_new_items_to_list(
        dst_path, answers_rel_path, varname, domains_version[version]
    )
