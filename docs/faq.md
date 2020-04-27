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
- [Why XML is broken after running pre-commit?](#why-xml-is-broken-after-running-pre-commit)

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
1. Visit `http://localhost:${ODOO_MAJOR}069` to see Odoo.
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
    image: traefik:1.6-alpine
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

![TODO](https://media.giphy.com/media/26gspO0c90QDHEQQ8/giphy.gif)

</details>

Then boot it up with:

```bash
docker-compose -p inverseproxy -f inverseproxy.yaml up -d
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
