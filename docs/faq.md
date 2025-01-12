# Frequently Asked Questions

Maybe not so frequent, but interesting anyway. 🤷

<details>
<!-- prettier-ignore-start -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<summary>Table of contents</summary>

- [Can I have my own private template?](#can-i-have-my-own-private-template)
- [Can I use environments for what they're not?](#can-i-use-environments-for-what-theyre-not)
- [How can I run a Posbox/IoT box service for development?](#how-can-i-run-a-posboxiot-box-service-for-development)
- [How can I whitelist a service and allow external access to it?](#how-can-i-whitelist-a-service-and-allow-external-access-to-it)
- [How do I develop for an external repo, such as OCA?](#how-do-i-develop-for-an-external-repo-such-as-oca)
- [How to bootstrap the global inverse proxy?](#how-to-bootstrap-the-global-inverse-proxy)
- [How to change report fonts?](#how-to-change-report-fonts)
- [How to get proper assets when printing reports?](#how-to-get-proper-assets-when-printing-reports)
- [How to have good QA and test in my CI with Doodba?](#how-to-have-good-qa-and-test-in-my-ci-with-doodba)
- [This project is too opinionated, but can I question any of those opinions?](#this-project-is-too-opinionated-but-can-i-question-any-of-those-opinions)
- [Where are screencasts and screenshots of my failed E2E tests?](#where-are-screencasts-and-screenshots-of-my-failed-e2e-tests)
  - [How to get screencasts and screenshots of failed E2E tests in Odoo 12.0?](#how-to-get-screencasts-and-screenshots-of-failed-e2e-tests-in-odoo-120)
- [How to use with podman?](#how-to-use-with-podman)
- [Why pre-commit fails each time I copy or update the template?](#why-pre-commit-fails-each-time-i-copy-or-update-the-template)
- [Why XML is broken after running pre-commit?](#why-xml-is-broken-after-running-pre-commit)
- [Why is Odoo saying that its database is not initialized?](#why-is-odoo-saying-that-its-database-is-not-initialized)
- [Why do I get a "Connection Refused" error when trying to lauch the VSCode Firefox JS Debugger?](#why-do-i-get-a-connection-refused-error-when-trying-to-lauch-the-vscode-firefox-js-debugger)
- [Why don't I see my Firefox extensions while debugging?](#why-dont-i-see-my-firefox-extensions-while-debugging)
- [Why do I get a "Connection Refused" error when trying to lauch the VSCode Chrome JS Debugger?](#why-do-i-get-a-connection-refused-error-when-trying-to-lauch-the-vscode-chrome-js-debugger)
- [Why can't Firefox load the page after I start a debugging session?](#why-cant-firefox-load-the-page-after-i-start-a-debugging-session)
- [Why won't my program stop on the specified breakpoints when using Firefox?](#why-wont-my-program-stop-on-the-specified-breakpoints-when-using-firefox)
- [When upgrading from an old template, prettier fails badly. How to update?](#when-upgrading-from-an-old-template-prettier-fails-badly-how-to-update)
- [When upgrading from an old template, pre-commit fails to install. What can I do?](#when-upgrading-from-an-old-template-pre-commit-fails-to-install-what-can-i-do)
- [When upgrading from an old template, copier fails with 'Invalid answer "None"'. How to update?](#when-upgrading-from-an-old-template-copier-fails-with-invalid-answer-none-how-to-update)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- prettier-ignore-end -->
</details>

## Can I have my own private template?

Yes, and thanks to Copier, you can combine both in the same subproject.

Just make sure to use a separate answers file so both don't mix:

```bash
# For the 1st copy
copier --answers-file .copier-answers.private.yml copy gh:Tecnativa/private-template .
# For updates
copier --answers-file .copier-answers.private.yml update .
```

Check Copier docs for more details.

## Can I use environments for what they're not?

You want to know if you can use `devel.yaml` to serve a production instance?

Wel... yes, you _can_, but it's not recommended nor supported.

## How can I run a Posbox/IoT box service for development?

Posbox has special needs that are not useful for most projects, and is quite tightly
related to specific hardware and peripherals, so it makes not much sense to ship it by
default in this template.

However, for testing connection issues, developing, etc., you might want to boot a
resource-limited posbox instance imitation.

The best you can do is buy a Posbox/IoT box and peripherals and use it, but for quick
tests that do not involve specific hardware, you can boot it with Doodba by:

- Add the `apt` dependency `usbutils` (which contains `lsusb` binary).
- Add the `pip` dependencies `evdev` and `netifaces`.
- Add a `posbox` container, which:
  - Can read usb devices, privileged.
  - Loads at boot all required `hw_*` addons, except for `hw_posbox_upgrade`.
  - Exposes a port that doesn't conflict with Odoo, such as `8070` i.e.

<details>
<summary>Example patch</summary>

```diff
diff --git a/devel.yaml b/devel.yaml
index e029d48..2f800de 100644
--- a/devel.yaml
+++ b/devel.yaml
@@ -15,7 +15,7 @@ services:
             PORT: "6899 8069"
             TARGET: odoo

-    odoo:
+    odoo: &odoo
         extends:
             file: common.yaml
             service: odoo
@@ -53,6 +53,21 @@ services:
             # XXX Odoo v8 has no `--dev` mode; Odoo v9 has no parameters
             - --dev=reload,qweb,werkzeug,xml

+    posbox:
+        <<: *odoo
+        ports:
+            - "127.0.0.1:8070:8069"
+        privileged: true
+        networks: *public
+        volumes:
+            - ./odoo/custom:/opt/odoo/custom:ro,z
+            - ./odoo/auto/addons:/opt/odoo/auto/addons:rw,z
+            - /dev/bus/usb
+        command:
+            - odoo
+            - --workers=0
+            - --load=web,hw_proxy,hw_posbox_homepage,hw_scale,hw_scanner,hw_escpos,hw_blackbox_be,hw_screen
+
     db:
         extends:
             file: common.yaml
diff --git a/odoo/custom/dependencies/apt.txt b/odoo/custom/dependencies/apt.txt
index 8b13789..e32891b 100644
--- a/odoo/custom/dependencies/apt.txt
+++ b/odoo/custom/dependencies/apt.txt
@@ -1 +1 @@
+usbutils
diff --git a/odoo/custom/dependencies/pip.txt b/odoo/custom/dependencies/pip.txt
index e69de29..6eef737 100644
--- a/odoo/custom/dependencies/pip.txt
+++ b/odoo/custom/dependencies/pip.txt
@@ -0,0 +1,2 @@
+evdev
+netifaces
```

</details>

Once you apply those changes, to use it:

1. `invoke img-build --pull` to install the new dependencies.
1. `invoke start` to start all services.
1. Visit `http://localhost:8070` to see the posbox running.
1. Visit `http://localhost:${ODOO_MAJOR}069` to see Odoo (e.g.: `$ODOO_MAJOR` is `14` if
   deploying Odoo 14.0).
1. Install `point_of_sale` in Odoo.
1. Configure the POS in Odoo to connect to Posbox in `localhost:8070`.

Of course this won't be fully functional, but it will give you an overview on the posbox
stuff.

[Beware about possible mixed content errors](https://github.com/odoo/odoo/issues/3156#issuecomment-443727760).

## How can I whitelist a service and allow external access to it?

This can become useful when you have isolated environments (like in `devel.yaml` and
`test.yaml` by default) but you need to allow some external API access for them. I.e.,
you could use Google Fonts API for your customer's reports, and those reports would take
forever and end up rendering badly in staging environments.

In such case, we recommend using the
[tecnativa/whitelist](https://hub.docker.com/r/tecnativa/whitelist/) image. Read its
docs there.

## How do I develop for an external repo, such as OCA?

You can use the same subproject used to deploy to production.

However, you might find this pattern useful:

1. Have your own "development-only subproject". One per Odoo version.
1. Add the repo there to `addons.yaml`. For example, add `server-tools: ["*"]` to
   develop [OCA's server-tools](https://github.com/OCA/server-tools/).
1. Download code as usual.
1. Develop.
1. Push the PR to Github.
1. Open your production deployment and add that PR to `repos.yaml`.

## How to bootstrap the global inverse proxy?

This is needed for testing and production environments to be reachable.

Our supported proxy is Traefik. There must be one in each node.

To have it, use this `inverseproxy.yaml` file:

<details>
<summary>Traefik v1 docker compose</summary>

```yaml
version: "2.1"

services:
  proxy:
    image: docker.io/traefik:1.7-alpine
    networks:
      shared:
      private:
      public:
    volumes:
      - acme:/etc/traefik/acme:rw,Z
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - dockersocket
    restart: unless-stopped
    privileged: true
    tty: true
    command:
      - --ACME.ACMELogging
      - --ACME.Email=you@example.com
      - --ACME.EntryPoint=https
      - --ACME.HTTPChallenge.entryPoint=http
      - --ACME.OnHostRule
      - --ACME.Storage=/etc/traefik/acme/acme.json
      - --DefaultEntryPoints=http,https
      - --EntryPoints=Name:http Address::80 Redirect.EntryPoint:https
      - --EntryPoints=Name:https Address::443 TLS
      - --LogLevel=INFO
      - --Docker
      - --Docker.EndPoint=http://dockersocket:2375
      - --Docker.ExposedByDefault=false
      - --Docker.Watch

  dockersocket:
    image: tecnativa/docker-socket-proxy
    privileged: true
    networks:
      private:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      CONTAINERS: 1
      NETWORKS: 1
      SERVICES: 1
      SWARM: 1
      TASKS: 1
    restart: unless-stopped

networks:
  shared:
    internal: true
    driver_opts:
      encrypted: 1

  private:
    internal: true
    driver_opts:
      encrypted: 1

  public:

volumes:
  acme:
```

</details>

<details>
<summary>Traefik v2 docker compose</summary>

```yaml
version: "2.4"
services:
  proxy:
    image: traefik:2.4
    networks:
      shared:
        aliases: []
      private:
      public:
    volumes:
      - acme:/etc/traefik/acme:rw,Z
    ports:
      - 80:80
      - 443:443
    depends_on:
      - dockersocket
    restart: unless-stopped
    tty: true
    command:
      - "--entrypoints.web-insecure.address=:80"
      - "--entrypoints.web-main.transport.respondingTimeouts.idleTimeout=60s"
      - "--entrypoints.web-main.http.middlewares=global-error-502@docker"
      - "--log.level=info"
      - "--providers.docker.endpoint=http://dockersocket:2375"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.network=inverseproxy_shared"
      - "--providers.docker=true"
      - "--entrypoints.web-main.address=:443"
      - "--entrypoints.web-main.http.tls.certResolver=letsencrypt"
      - "--certificatesresolvers.letsencrypt.acme.caserver=https://acme-v02.api.letsencrypt.org/directory"
      - "--certificatesresolvers.letsencrypt.acme.email=alerts@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/etc/traefik/acme/acme-v2.json"
      - "--entrypoints.web-insecure.http.redirections.entryPoint.to=web-main"
      - "--entrypoints.web-insecure.http.redirections.entryPoint.scheme=https"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web-insecure"
  dockersocket:
    image: tecnativa/docker-socket-proxy
    privileged: true
    networks:
      private:
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
    environment:
      CONTAINERS: 1
      NETWORKS: 1
      SERVICES: 1
      SWARM: 1
      TASKS: 1
    restart: unless-stopped
  error-handling:
    image: nginx:alpine
    restart: unless-stopped
    networks:
      - shared
    volumes:
      - error-handling-config:/etc/nginx/conf.d/
      - error-handling-data:/usr/share/nginx/html/
    labels:
      traefik.docker.network: inverseproxy_shared
      traefik.enable: "true"
      traefik.http.routers.error-handling.rule: HostRegexp(`{any:.+}`)
      traefik.http.routers.error-handling.entrypoints: web-main
      traefik.http.routers.error-handling.priority: 1
      traefik.http.routers.error-handling.service: global-error-handler
      traefik.http.routers.error-handling.middlewares: global-error-502
      traefik.http.middlewares.global-error-502.errors.status: 502
      traefik.http.middlewares.global-error-502.errors.service: global-error-handler
      traefik.http.middlewares.global-error-502.errors.query: "/{status}.html"
      traefik.http.services.global-error-handler.loadbalancer.server.port: 80
networks:
  shared:
    internal: true
    driver_opts:
      encrypted: 1
  private:
    internal: true
    driver_opts:
      encrypted: 1
  public:
    driver_opts:
      encrypted: 1
volumes:
  acme:
  error-handling-config:
  error-handling-data:
```

</details>

<details>
<summary>Traefik v3 docker compose</summary>

```yaml
version: "2.4"
services:
  proxy:
    image: traefik:3.0
    networks:
      shared:
        aliases: []
      private:
      public:
    volumes:
      - acme:/etc/traefik/acme:rw,Z
    ports:
      - 80:80
      - 443:443
      - 5432:5432 # Add this port for direct database access
    depends_on:
      - dockersocket
    restart: unless-stopped
    environment:
      AWS_ACCESS_KEY_ID: ""
      AWS_SECRET_ACCESS_KEY: ""
      LEGO_EXPERIMENTAL_CNAME_SUPPORT: "true"
    tty: true
    command:
      - "--entrypoints.web-insecure.address=:80"
      - "--entrypoints.web-main.transport.respondingTimeouts.idleTimeout=60s"
      - "--entrypoints.web-main.http.middlewares=global-error-502@docker"
      - "--log.level=info"
      - "--providers.docker.endpoint=http://dockersocket:2375"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.network=inverseproxy_shared"
      - "--providers.docker=true"
      - "--entrypoints.web-main.address=:443"
      - "--entrypoints.web-main.http.tls.certResolver=letsencrypt"
      - "--certificatesresolvers.letsencrypt.acme.caserver=https://acme-v02.api.letsencrypt.org/directory"
      - "--certificatesresolvers.letsencrypt.acme.email=alerts@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/etc/traefik/acme/acme-v2.json"
      - "--entrypoints.web-insecure.http.redirections.entryPoint.to=web-main"
      - "--entrypoints.web-insecure.http.redirections.entryPoint.scheme=https"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web-insecure"
      - "--entrypoints.postgres-entrypoint.address=:5432" # Define entrypoint for PostgreSQL for direct database access
  dockersocket:
    image: tecnativa/docker-socket-proxy
    privileged: true
    networks:
      private:
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
    environment:
      CONTAINERS: 1
      NETWORKS: 1
      SERVICES: 1
      SWARM: 1
      TASKS: 1
    restart: unless-stopped
  error-handling:
    image: nginx:alpine
    restart: unless-stopped
    networks:
      - shared
    volumes:
      - error-handling-config:/etc/nginx/conf.d/
      - error-handling-data:/usr/share/nginx/html/
    labels:
      traefik.docker.network: inverseproxy_shared
      traefik.enable: "true"
      traefik.http.routers.error-handling.rule: HostRegexp(`{any:.+}`)
      traefik.http.routers.error-handling.entrypoints: web-main
      traefik.http.routers.error-handling.priority: 1
      traefik.http.routers.error-handling.service: global-error-handler
      traefik.http.routers.error-handling.middlewares: global-error-502
      traefik.http.middlewares.global-error-502.errors.status: 502
      traefik.http.middlewares.global-error-502.errors.service: global-error-handler
      traefik.http.middlewares.global-error-502.errors.query: "/{status}.html"
      traefik.http.services.global-error-handler.loadbalancer.server.port: 80
networks:
  shared:
    internal: true
    driver_opts:
      encrypted: 1
  private:
    internal: true
    driver_opts:
      encrypted: 1
  public:
    driver_opts:
      encrypted: 1
volumes:
  acme:
  error-handling-config:
  error-handling-data:
```

</details>

Then boot it up with:

```bash
docker compose -p inverseproxy -f inverseproxy.yaml up -d
```

This will intercept all requests coming from port 80 (HTTP) and redirect them to port
443 (HTTPS), it will download and install required TLS certificates from
[Let's Encrypt](https://letsencrypt.org/) whenever you boot a new instance, add the
required proxy headers to the request, and then redirect all traffic to/from odoo
automatically.

It includes
[a security-enhaced proxy](https://hub.docker.com/r/tecnativa/docker-socket-proxy/) to
reduce attack surface when listening to the Docker socket.

This allows you to:

- Have multiple domains for each Odoo instance.
- Have multiple Odoo instances in each node.
- Add an TLS layer automatically and for free.

## How to change report fonts?

Doodba ships [Liberation fonts](https://wikipedia.org/wiki/Liberation_fonts) as
defaults.

If you want to make another font package _available_, just add it to
[`apt.txt`][dependencies] (if it's a normal Debian package) or install it in a [custom
build script][build.d] called i.e. `build.d/200-custom-fonts` (if you need to install it
in a more complex way).

If, in addition to that, you want those fonts to be the _defaults_, then add one (or
more) of these build arguments:

- `FONT_MONO`
- `FONT_SANS`
- `FONT_SERIF`

## How to get proper assets when printing reports?

Make sure there's a `ir.config_parameter` called `report.url` with the value
`http://localhost:8069`.

## How to have good QA and test in my CI with Doodba?

Inside this image, there's the `/qa` folder, which provides some necessary plumbing to
perform quality assurance and continous integration if you use [doodba-qa][], which is a
separate (but related) project with that purpose.

Go there to get more instructions.

## This project is too opinionated, but can I question any of those opinions?

Of course. There's no guarantee that we will like it, but please do it. 😉

## Where are screencasts and screenshots of my failed E2E tests?

Starting with Odoo (and Doodba) 13.0, when you're in [the devel
environment][development] and run some E2E test (tours, JS tests...) that fails, Odoo
will output screenshots and screencasts automatically. These are very useful for
debugging.

You can find them in the `./odoo/auto/test-artifacts` directory in your development
host. No need to sniff around inside the container to find them.

### How to get screencasts and screenshots of failed E2E tests in Odoo 12.0?

In Odoo (and Doodba) 12.0, the screencasts and screenshots feature is also supported,
but it is less intuitive: just apply this patch to your `devel.yaml` file:

```diff
diff --git a/devel.yaml b/devel.yaml
index 2026e7c..d4e5a68 100644
--- a/devel.yaml
+++ b/devel.yaml
@@ -60,6 +60,7 @@ services:
       - --limit-time-real=9999999
       - --workers=0
       - --dev=reload,qweb,werkzeug,xml
+      - --logfile=/opt/auto/test-artifacts/odoo.log

   db:
     extends:
```

You'll find Odoo logs in `./odoo/auto/test-artifacts/odoo.log` file, and screencasts and
screenshots will be around with some weird names. As a side effect, your container will
output no logs to the console.

Since this is an awkward side effect of that setting, we're not shipping that by
default.

## How to use with podman?

Podman 4+ is supported for development, provided you follow these instructions.

Example usage:

```sh
# Install dependencies
sudo dnf -y install podman podman-docker docker-compose
# Make sure podman works
podman run --rm hello-world
# Install rootless podman backend socket replacement
systemctl enable --user --now podman.socket
# Instruct docker clients to connect to podman backend
export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock
# Instruct git-aggregator to use inner UID and GID 0, which podman will map to your user
export DOODBA_GITAGGREGATE_UID=0 DOODBA_GITAGGREGATE_GID=0 DOODBA_UMASK=22
```

Once all that is done, continue with normal workflow on that terminal.

Add those exports to your bash profile to avoid repeating them for each terminal. If you
use `fish`, it's easier:

```fish
# Fish-only syntax to save all those exports permanently
set --universal --export DOCKER_HOST unix:///run/user/(id -u)/podman/podman.sock
set --universal --export DOODBA_GITAGGREGATE_UID 0
set --universal --export DOODBA_GITAGGREGATE_GID 0
set --universal --export DOODBA_UMASK 22
```

Then continue with the [instructions for daily usage](daily-usage.md).

## Why pre-commit fails each time I copy or update the template?

We format here YAML files using [Prettier](https://prettier.io/) inside
[pre-commit](https://pre-commit.com/).

However, when the template is generated, you have a lot of chances that your YAML files
are badly formatted. For instance, depending on the length of you alternate domains,
Traefik rules might be longer or shorter, triggering a different reformat on each
project, or on each update. That is expected good behavior.

Also, the way Copier formats your `.copier-answers.yml` file almost always violates
Prettier's rules.

So, if you find out that after generating the project for the 1st time, or after
updating it, it fails pre-commit validations, don't worry about that. Just let
pre-commit reformat your files in next commit, and commit again.

Quick dirty recipe:

```bash
copier --force update
git add .
pre-commit run
git add .
git commit -m 'Update from template'
```

## Why XML is broken after running pre-commit?

Doodba Copier Template enables [Prettier](https://prettier.io/) as a
[pre-commit](https://pre-commit.com/) formatter for many file formats. One of these is
XML, and we configure Prettier with `xmlWhitespaceSensitivity: "ignore"`. This is like
telling Prettier: "do whatever you need with XML whitespace to prettify XML files".

We do this because most times XML whitespace is meaningless, and prettifying a file
without changing whitespace limits _a lot_ what Prettier can do. However, keep in mind
that _in some cases, it can be meaningful_.

We sometimes use XML in Odoo to generate HTML. In HTML, whitespace matters at least in
these cases:

1. Inside
   [the `<pre>` element](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/pre).
1. When any element uses
   [the CSS `white-space` style](https://developer.mozilla.org/en-US/docs/Web/CSS/white-space)
   with certain values.

So, if you see that after running `pre-commit` some HTML is broken, this is possibly the
cause.

Our recommendation is that, at least, before you run it for the 1st time, search `<pre`
(literally) among your private modules, and in case you find any, be careful about what
Prettier does with them.

If you install Fish, you can run these commands to find those dangerous things. If one
fails with `No matches for wildcard`, it means there are no files to check and thus you
can ignore that error:

```bash
cd $project_root/odoo/custom/src/private
fish -c 'grep "<pre" **.{xml,html}'
fish -c 'grep -E "white-space:\s*(pre|break-spaces)" **.{less,sass,scss,css}'
```

You can wrap any XML code among [ignore tags](https://prettier.io/docs/en/ignore.html)
to tell Prettier "don't touch this":

```xml
<!-- prettier-ignore-start -->
<pre>
________________
|              |
|    DOODBA    |
|    RULEZ!    |
|______________|
(\_/)  ||
(•ㅅ•) ||
/ 　 づ
</pre>
<!-- prettier-ignore-end -->
```

You can also replace our default for `xmlWhitespaceSensitivity: "strict"` inside your
`.prettierrc.yml` file.

## Why is Odoo saying that its database is not initialized?

This is a common problem within the development workflow. From Odoo 12.0, the database
needs to be initialized by hand. You can know that you're facing this problem if you see
in Odoo's logs something like this:

```log
2020-06-09 10:24:26,715 1 ERROR ? odoo.modules.loading: Database devel not initialized, you can force it with `-i base`
2020-06-09 10:25:26,781 1 ERROR devel odoo.sql_db: bad query: SELECT latest_version FROM ir_module_module WHERE name='base'
ERROR: relation "ir_module_module" does not exist
LINE 1: SELECT latest_version FROM ir_module_module WHERE name='base...
                                   ^
```

You can do as **the log is clearly telling you to do** (side note: READ THE LOGS! 😀):

```bash
docker compose run --rm odoo --stop-after-init -i base
invoke restart
```

Or you can use the `resetdb` task to reset your `devel` database:

```bash
invoke resetdb
```

If you use this method, Odoo will have 2 databases created. You should use the one
called `devel`; the other one is just a cache, so the next time you run this command
it's faster.

This is just a helper over these tools, which you might want to use directly instead:

- [`click-odoo-dropdb`](https://github.com/acsone/click-odoo-contrib#click-odoo-dropdb-stable)
- [`click-odoo-initdb`](https://github.com/acsone/click-odoo-contrib#click-odoo-initdb-stable)

## Why do I get a "Connection Refused" error when trying to lauch the VSCode Firefox JS Debugger?

When using Firefox as the debugging browser, this may be happening because the path for
its executable is misconfigured.

To fix this, change the `firefoxExecutable` variable for the
[VS Code Debugger for Firefox](https://github.com/firefox-devtools/vscode-firefox-debug)
extension under Settings to your Firefox executable path. To find it, you can run:

```bash
which firefox
```

Then, add the following to your **global** `settings.json` file:

```json
{
  // ...
  "firefox.executable": "/usr/bin/firefox"
  // ...
}
```

## Why don't I see my Firefox extensions while debugging?

Firefox may load a different user profile than your personal one.

To fix that, add the following to your **global** `settings.json` file:

```json
{
  // ...
  "firefox.profile": "default-release"
  // ...
}
```

_Notes:_

- Your profile might be named differently. You can visit `about:profiles` from firefox
  to list them.
- The extension is in reality using a temporary copy of that profile, so any changes you
  do to it won't be saved unless you configure it with
  `"firefox.keepProfileChanges": true`. If you enable that option, you may prefer using
  a profile named differently than your default one, so you can have 2 Firefox instances
  running in parallel and don't need to stop Firefox to restart it again in debug mode.

## Why do I get a "Connection Refused" error when trying to lauch the VSCode Chrome JS Debugger?

When using Chrome as the debugging browser, this may be happening because the path for
its executable is misconfigured.

To fix this, you must have either **Chrome** or **Chromium** installed in your system.

The Chrome executable will be selected by default and, if not installed, Chromium will
be selected. Make sure you have the respective executable in your `$PATH`.

## Why can't Firefox load the page after I start a debugging session?

It is possible that the page is not ready yet. Wait a couple of seconds and reload.

## Why won't my program stop on the specified breakpoints when using Firefox?

When debugging, you must have `debug=assets` in your Odoo URL. By default, when you
launch a debugging session, VSCode will open you browser in a new window with the
correct URL. However, if you need to log in, you loose that URL. To avoid that, make
sure you are not losing your cookies each time you reload a debugging session. (See
[Why don't I see my Firefox extensions while debugging?](#Why-don't-I-see-my-Firefox-extensions-while-debugging?)
for how to set up your Firefox debugging profile)

## When upgrading from an old template, prettier fails badly. How to update?

Whether it was prettier, npm, nodejs or whoever else, the fact is that
[recently there happened a prettiermageddon](https://github.com/prettier/prettier/issues/9459).

When you're updating from an older template to a newer, Copier will try to produce a
vanilla project with the old template before updating it, to be able to extract a smart
diff and apply the required changes to your subproject.

Since old versions of the template are broken due to this prettier problem, you cannot
update anymore. Well, here's the workaround:

1.  Indicate to [nodeenv](http://ekalinin.github.io/nodeenv/) that your default nodejs
    version is 14.14.0 by creating a file in `~/.nodeenvrc` with the following contents.
    This will avoid the problem of prettier being unable to install:

    ```ini
    [nodeenv]
    node = 14.14.0
    ```

1.  Update to latest template
    [skipping `prettier` hook](https://pre-commit.com/#temporarily-disabling-hooks).
    This will avoid the problem of prettier + plugin-xml being unable to execute, even
    if properly installed:

    ```bash
    env SKIP=prettier copier update
    ```

Once all your doodba subprojects are on template v2.5.0 or later, you won't need the
`~/.nodeenvrc` anymore (hopefully) and you can safely delete it, as node version is
pinned there and we install prettier from
[their new specific pre-commit repo](https://github.com/prettier/pre-commit).

## When upgrading from an old template, pre-commit fails to install. What can I do?

Due to the
[latest updates to the `pip` dependency resolver](https://pip.pypa.io/en/latest/user_guide/#changes-to-the-pip-dependency-resolver-in-20-2-2020),
some packages fail to install.

As with the recent
[prettiermageddon](#when-upgrading-from-an-old-template-prettier-fails-badly-how-to-update),
when you're updating from an older template to a newer, Copier will try to produce a
vanilla project with the old template before updating it, to be able to extract a smart
diff and apply the required changes to your subproject.

Since old versions of the template might be broken if you are running the latest `pip`
version, you cannot update anymore. Where is what you can do to avoid it:

1.  Since `pre-commit` manages it's dependencies with `python-virtualenv`, you can
    indicate which version of pip it should use. There are several ways of doing it, but
    the easiest is with an environment variable. Just pass `VIRTUALENV_PIP=20.2` before
    any command that fails due to this problem. For example, when running a copier
    update:

    ```bash
    env VIRTUALENV_PIP=20.2 copier update
    ```

Once all your doodba subprojects are on template v2.6.1 or later, you shouldn't have
this problem, as the pre-commit hook's versions and dependencies where tailored to work
with these new constraints.

## When upgrading from an old template, copier fails with 'Invalid answer "None"'. How to update?

When you're updating from an older template to a newer, Copier will try to produce a
vanilla project with the old template before updating it, to be able to extract a smart
diff and apply the required changes to your subproject.

Since old versions of the template are broken due to this copier problem, you cannot
update anymore. Well, here's the workaround:

1. Launch 'recopy': `copier recopy --trust -f .`
2. Save the name of the question that gives the problem (for example 'odoo_oci_image')
3. Launch 'recopy' again but with an empty string as the default value for the
   problematic question: `copier recopy --trust -f -d odoo_oci_image='' .`
4. Repeat the steps expanding in point 4 with as many questions as you need:
   `-d var1='' -d var2=[] ...`

For example, getting this error:
`copier.errors.InvalidTypeError: Invalid answer "None" of type "<class 'NoneType'>" to question "gitlab_url" of type "str"`
You can see the name of the problematic question (gitlab_url) and its type (str).

Normally the conversion would look something like this:

| Question Type | New value to use with -d |
| ------------- | ------------------------ |
| str           | ''                       |
| yaml          | {}                       |
| int           | 0                        |
| float         | 0                        |
| json          | {}                       |
| bool          | false                    |
