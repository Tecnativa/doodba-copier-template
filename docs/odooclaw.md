<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<summary>Table of contents</summary>

- [OdooClaw AI agent](#odooclaw-ai-agent)
  - [What was generated](#what-was-generated)
  - [First-time setup](#first-time-setup)
  - [How it works](#how-it-works)
  - [Changing the provider or model](#changing-the-provider-or-model)
  - [Disabling](#disabling)
  - [Docs](#docs)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# OdooClaw AI agent

This project was generated with `use_odooclaw: true`, which wires
[OdooClaw](https://github.com/nicolasramos/odooclaw) — a fully local AI agent that
answers `@OdooClaw` mentions in Odoo Discuss — into your Doodba stack.

> **Odoo 16, 17 and 18 only.** The OdooClaw Odoo modules are published per Odoo version,
> so `use_odooclaw` is only offered when generating a project for those versions. On any
> other version the question is hidden and no OdooClaw files are generated.

## What was generated

| Piece                                  | Where                                                                                        |
| -------------------------------------- | -------------------------------------------------------------------------------------------- |
| Gateway source (compose build context) | `odooclaw/` (populated by `scripts/setup-odooclaw.sh`; only `config/config.json` is tracked) |
| Gateway config                         | `odooclaw/config/config.json`                                                                |
| Secrets/env                            | `.docker/odooclaw.env`                                                                       |
| Compose services (`odooclaw`, `redis`) | inline in `devel.yaml` / `prod.yaml`                                                         |
| Odoo module repo                       | `odoo/custom/src/repos.yaml` (`nicolasramos/odoo-addons`, branch = your Odoo version)        |
| Bootstrap / smoke test                 | `scripts/setup-odooclaw.sh`, `scripts/smoke-test-odooclaw.sh`                                |

The generated `README.md` deliberately carries **no** OdooClaw section: markdown is not
byte-stable across renders (this template formats it with `proseWrap: always`), so a
conditional section makes `copier update` produce an unresolved `README.md` conflict
that blocks `git commit` when you flip the option. This document and the output of
`scripts/setup-odooclaw.sh` are the entry points instead.

## First-time setup

1. **Fetch the gateway source** (the compose file builds the `odooclaw` image from
   `./odooclaw`, it is not published as a Docker image):

   ```bash
   scripts/setup-odooclaw.sh
   ```

2. **Set secrets** in `.docker/odooclaw.env` (never commit this file):

   - `ODOOCLAW_PROVIDERS_<PROVIDER>_API_KEY` — your provider API key (leave it empty for
     a keyless local Ollama).
   - `ODOO_USERNAME` / `ODOO_PASSWORD` — an Odoo user the `odoo-mcp` tools can use. It
     ships as `admin` + Doodba's `odoo_admin_password`; a dedicated technical user is
     recommended for anything beyond a local try-out (see
     [ODOO_TECHNICAL_USER.md](https://github.com/nicolasramos/odooclaw/blob/main/odooclaw/docs/ODOO_TECHNICAL_USER.md)).

   ⚠️ Write every value **literally** in that file. Docker compose reads an `env_file`
   verbatim: a `${VAR}` reference inside it is resolved from your shell or from the
   project `.env`, never from the file itself, so something like
   `ODOOCLAW_PROVIDERS_OPENAI_API_KEY=${ODOOCLAW_LLM_API_KEY:-}` silently ends up empty
   and the agent never answers.

3. **Start the stack**:

   ```bash
   docker compose -f devel.yaml build odooclaw
   docker compose -f devel.yaml up -d
   ```

4. **Install the Odoo module**: in Odoo, Apps → search "OdooClaw" → install
   `mail_bot_odooclaw` (plus the area modules you want: `_account`, `_crm`, `_expense`,
   `_fleet` — available on the 18.0 branch).

5. **Smoke test**:

   ```bash
   scripts/smoke-test-odooclaw.sh devel.yaml
   ```

6. **Chat**: open a DM in Discuss and type `@OdooClaw hello`.

## How it works

```
DM in Odoo → mail_bot_odooclaw (overrides message_post)
           → POST http://odooclaw:18790/webhook/odoo (async)
           → OdooClaw agent + odoo-mcp tools (respect the user's permissions)
           → reply posted back to the same Discuss conversation
```

The database the agent talks to is pinned per environment by
`ODOOCLAW_CHANNELS_ODOO_TARGET_DB` (`devel` in `devel.yaml`, `{{ postgres_dbname }}` in
`prod.yaml`), so the agent never resolves the wrong DB.

## Changing the provider or model

`odooclaw_provider` / `odooclaw_model` are copier answers. Change them with:

```bash
copier copy --defaults -d odooclaw_provider=ollama -d odooclaw_model=llama3 . <new-dir>
# or edit .copier-answers.yml and run: copier copy --defaults ...
```

## Disabling

Set `use_odooclaw: false` in `.copier-answers.yml` and run `copier update`. The
after-update task strips the OdooClaw blocks from `repos.yaml`/`addons.yaml`, removes
the generated scripts and deletes the whole `odooclaw/` tree — the generated
`config.json` and, if you had run `scripts/setup-odooclaw.sh`, the fetched gateway
source as well. That source is pure cache: enable the option again and re-run the script
to fetch it back. (Leaving the tree behind with an ignore file was the obvious
alternative, but copier applies its own deletions _after_ `after-update` runs, so the
ignore file would not survive the update and every third-party file would become
committable.)

Before running it, one more thing copier itself does with the files it stops generating:

- **`.docker/odooclaw.env` is deleted** (copier removes whatever it generated and no
  longer generates). Copy it aside first if you want to keep your API key and
  credentials — nothing else in the project holds them.

## Docs

Upstream documentation lives in
<https://github.com/nicolasramos/odooclaw/tree/main/odooclaw/docs>, including
`GUIDE_DOODBA_SETUP_EN.md` and `GUIA_DOODBA_PUESTA_EN_MARCHA_ES.md`.
