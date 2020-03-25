[![Doodba deployment](https://img.shields.io/badge/deployment-doodba-informational)][doodba]
[![Copier template](https://img.shields.io/badge/template%20engine-copier-informational)][copier]
[![Boost Software License 1.0](https://img.shields.io/badge/license-bsl--1.0-important)](COPYING)
![latest version](https://img.shields.io/github/v/release/Tecnativa/doodba-copier-template?sort=semver)
![test](https://github.com/Tecnativa/doodba-copier-template/workflows/test/badge.svg)
![lint](https://github.com/Tecnativa/doodba-copier-template/workflows/lint/badge.svg)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

# Doodba Copier Template

This project lets you maintain [Odoo][] deployments based on [Doodba][] using
[Copier][].

<details>
<!-- prettier-ignore-start -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<summary>Table of contents</summary>

- [Installation and Usage](#installation-and-usage)
- [Getting Updates](#getting-updates)
- [Contributing](#contributing)
- [Credits](#credits)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- prettier-ignore-end -->
</details>

# Installation and Usage

This project itself is just the template, but you need to install these tools to use it:

- [copier][] v3.0.0 or newer
- [git](https://git-scm.com/)
- [invoke](https://www.pyinvoke.org/) installed in Python 3.6+ (and the binary must be
  called `invoke` — beware if your distro installs it as `invoke3` or similar).
- [pre-commit](https://pre-commit.com/)
- [python](https://www.python.org/) 3.6+

Install non-python apps with your distro's recommended package manager. The recommended
way to install Python CLI apps is [pipx](https://pipxproject.github.io/pipx/):

```bash
python3 -m pip install --user pipx
pipx install copier
pipx install invoke
pipx install pre-commit
pipx ensurepath
```

Once you installed everything, you can now use Copier to copy this template:

```bash
copier copy gh:Tecnativa/doodba-copier-template ~/path/to/your/downstream/scaffolding
```

Copier will ask you a lot of questions. Answer them to properly generate the template.

# Getting Updates

⚠️ If you come from
[doodba-scaffolding](https://github.com/Tecnativa/doodba-scaffolding), please follow
[the migration guide](docs/migrating-from-doodba-scaffolding.md).

If you always used Copier with this project, getting last updates with Copier is simple:

```bash
cd ~/path/to/your/downstream/scaffolding
copier update
```

Copier will ask you all questions again, but default values will be those you answered
last time. Just hit <kbd>Enter</kbd> to accept those defaults, or change them if
needed... or you can use `copier --force update` instead to avoid answering again all
things.

Basically, read Copier docs and `copier --help-all` to know how to use it.

# Contributing

See the [contribution guidelines](CONTRIBUTING.md).

# Credits

This project is maintained by:

[![Tecnativa](https://www.tecnativa.com/r/H3p)](https://www.tecnativa.com/r/rIN)

Also, special thanks to
[our dear community contributors](https://github.com/Tecnativa/doodba-copier-template/graphs/contributors).

[copier]: https://github.com/pykong/copier
[doodba]: https://github.com/Tecnativa/doodba
[odoo]: https://www.odoo.com/
