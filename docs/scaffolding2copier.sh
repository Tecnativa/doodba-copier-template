#!/usr/bin/env bash

# Simple script to ease migration from doodba-scaffolding to doodba-copier-template.
# Configure it exporting these environment variables:
# - `CUSTOM_COPIER_FLAGS` lets you configure this transition. Use `--force` to avoid
#   Copier asking you things, if you are confident in the answers provided here.
# - `TEMPLATE_VERSION` the only supported version to migrate from doodba-scaffolding
#   is the default one set here, but you can use others at your own risk.
# - `GITLAB_PREFIX`
# - `LICENSE`
# - `PROJECT_NAME` defaults to the current folder name.

source .env
copier $CUSTOM_COPIER_FLAGS \
  -r "${TEMPLATE_VERSION-v1.8.1}" \
  -d project_name="${PROJECT_NAME-$(basename $PWD)}" \
  -d project_license="${LICENSE-BSL-1.0}" \
  -d gitlab_url="${GITLAB_PREFIX-https://gitlab.com/example}/${PROJECT_NAME-$(basename $PWD)}" \
  -d domain_prod="$DOMAIN_PROD" \
  -d domain_prod_alternatives="[$DOMAIN_PROD_ALT]" \
  -d domain_test="$DOMAIN_TEST" \
  -d odoo_version="$ODOO_MINOR" \
  -d odoo_initial_lang="$INITIAL_LANG" \
  -d odoo_oci_image="$ODOO_IMAGE" \
  -d odoo_dbfilter="$DB_FILTER" \
  -d odoo_proxy=traefik \
  -d postgres_version="$DB_VERSION" \
  -d postgres_username="$DB_USER" \
  -d postgres_dbname="prod" \
  -d traefik_version="$TRAEFIK_VERSION" \
  -d smtp_default_from="$SMTP_DEFAULT_FROM" \
  -d smtp_relay_host="$SMTP_REAL_RELAY_HOST" \
  -d smtp_relay_port="$SMTP_REAL_RELAY_PORT" \
  -d smtp_relay_user="$SMTP_REAL_RELAY_USER" \
  -d smtp_canonical_default="$SMTP_REAL_NON_CANONICAL_DEFAULT" \
  -d smtp_canonical_domains="[$SMTP_REAL_CANONICAL_DOMAINS]" \
  -d backup_dst="boto3+s3://$BACKUP_S3_BUCKET" \
  -d backup_email_from="$BACKUP_EMAIL_FROM" \
  -d backup_email_to="$BACKUP_EMAIL_TO" \
  -d backup_deletion=false \
  -d backup_tz="$BACKUP_TZ" \
  update
