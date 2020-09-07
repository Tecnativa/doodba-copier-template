# Migrating From Doodba Scaffolding

<details>
<!-- prettier-ignore-start -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<summary>Table of contents</summary>

- [Why we needed something better](#why-we-needed-something-better)
- [How to transition to doodba-copier-template](#how-to-transition-to-doodba-copier-template)
- [What changes for you now](#what-changes-for-you-now)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- prettier-ignore-end -->
</details>

Welcome to the migration guide for previous
[doodba-scaffolding](https://github.com/Tecnativa/doodba-scaffolding) users.

I know, I know... you are used to do `git pull scaffolding master` to update your
templates, and now you wonder why now all is more complicated... Let me explain.

## Why we needed something better

Before we started using [Copier](https://github.com/pykong/copier),
[the official instructions](https://github.com/Tecnativa/doodba/blob/dbaaa2782a2d00e093063ebee3478c1d4093def3/README.md#skip-the-boring-parts)
were, basically:

1. Git-clone the scaffolding.
1. Search for comments containing the string `XXX`.
1. Modify at will.
1. If you want to update your scaffolding, just pull again and resolve conflicts.

This presented a lot of problems that Copier solves:

1. Your downstream project git history was flooded with commits from the upstream
   doodba-scaffolding project.
1. No possibility to apply logic to the template. This was becoming a problem as good
   tools arised. For example, pre-commit can add or remove the `# -*- coding: utf-8 -*-`
   comment to your source files, but the rule should be add in Python 2 (Odoo < 11.0)
   and remove in Python 3 (Odoo >= 11.0). But `.pre-commit-config.yaml` is a static
   file, so no way to include that 🤷.
1. No way to update a default value without breaking some production deployments.
   Example:
   [when we upgraded the default postgres version](https://github.com/Tecnativa/doodba/issues/67#issuecomment-413460188).
1. Adding a good README to this project would mean replicating it everywhere, so
   sometimes the barrier between doodba and doodba-scaffolding projects was blurry.
1. Possibly more problems.

Now, with Copier, these problems are (or _can_ be) solved. However, now you must do some
special extra steps to transition to the new workflow:

## How to transition to doodba-copier-template

Now let's upgrade your downstream scaffolding to the latest version. This is required
because the latest version _is the only one prepared to make transition to copier
easier_.

```bash
# In case you didn't do these before...
cd ~/path/to/your/downstream/scaffolding
git remote add scaffolding https://github.com/Tecnativa/doodba-scaffolding.git
# The important one
git pull scaffolding master
```

If you have git conflicts, solve them and commit:

```bash
git mergetool # Or solve conflicts manually if you prefer
git add .
git merge --continue
```

You will never need again to pull from doodba-scaffolding, so let's remove that remote:

```bash
git remote rm scaffolding
```

Now it's time to prepare this scaffolding to be upgraded.

The first pain point you will experience is that **YAML and JSON files will be now
indented using 2 spaces** instead of 4. Here's a little suggestion to avoid some nasty
diffs when doing this upgrade, but it will cost you 1 commit. If you prefer, you can
choose to skip this step and solve conflicts manually later, but be aware they'll be _A
LOT_:

```bash
sed -i 's/    /  /g' .vscode/*.{json,code-snippets} *.yaml odoo/custom/src/*.yaml
git commit -am '[DCK] Indent YAML and JSON files with 2 spaces'
```

OK, you're ready to use copier for the first time, so
[make sure you installed all you need](../README.md#installation-and-usage) and
continue:

```bash
copier update
```

Copier will ask you a lot of questions. **Your answers must match what you already have
in your scaffolding**, or otherwise the update could be problematic.

<details>
<summary>Copier asks too many questions; I want a faster but less secure way to do it.</summary>

You can use [this little script](./scaffolding2copier.sh) to make your transition
easier. It will _try_ to get values from your current scaffolding and apply them to
copier. **Take it as just a simple helper, but this doesn't save you the transition
responsibility**, because the possible customizations in a scaffolding are basically
endless. Inspect its code to understand the environment variables that can alter its
behavior. Run it like this:

```bash
bash -c 'source <(curl -sSL https://raw.githubusercontent.com/Tecnativa/doodba-copier-template/stable/docs/scaffolding2copier.sh)'
```

If anything goes wrong, reset and use the manual way:

```bash
git reset --hard
git clean -ffd
```

</details>

Now, it's time for conflict resolution (again):

- Copier tried to solve most conflicts for you, but it saves what it can't solve in
  `*.rej` files. Those are forbidden, but meaningful. If there's any, it means there's
  some unresolved diff you should review manually. Search for them manually and **review
  those conflicts**. When you finish, **remove those files** or you won't be able to
  commit.

- Apart from that, review all `git diff`. It's a lot! But it will help you.
  [Read below to understand that diff](#what-changes-for-you-now).

  You can use `git difftool` to launch your favorite diff tool and inspect it more
  comfortably.

After you've finished solving all conflicts and are happy with the result, commit it:

```bash
git add .
# This command could fail if pre-commit reformats any files; if so, repeat it twice
git commit -am '[DCK] Upgrade from doodba-scaffolding to doodba-copier-template'
# Format all other files (private modules, custom configs...) and commit that separately
pre-commit run -a
git commit -am '[IMP] 1st pre-commit execution'
```

⚠️ Read
[this warning about XML whitespace](faq.md#why-xml-is-broken-after-running-pre-commit)
⚠️

Your transition is finished! 🎉

## What changes for you now

After finishing, you will notice some important differences:

- Many `XXX` comments are removed because now there's no need for them.
- `LICENSE` might have changed if you didn't provide a valid value in the
  `copier update` step above.
- In `.env` and `prod.yaml`, `BACKUP_S3_BUCKET` is replaced for `BACKUP_DST`, which is
  more generic.
- In `prod.yaml`, `traefik.alt` labels are now `traefik.alt-0`, because now several alt
  domains are supported.
- `README.md` is completely changed.
- A new `.copier-answers.yml` file has been created, with all your answers. It is
  important that you **don't change this file manually and add it to your next commit**,
  because it will make further updates work as expected.
- You have a lot of new configs for linters and formatters, including the almighty
  `.pre-commit-config.yaml` file, which is enabled by default for you. Your code will
  look awesome now!
- OTOH some other configs and helpers are removed, namely:
  - `.vscode/doodba/`
  - `.vscode/doodbasetup.py`
  - `.travis.yml` is removed to avoid your child project including some unnecessary
    configurations, but in case you modified it before and need it, just restore it.
- There's a new `tasks.py` file ready to be used from the `invoke` command that you
  previously installed. Let's use it!

  ```bash
  # This will set up your development environment (although it's done for you already 😉)
  invoke develop
  # This will download git code
  invoke git-aggregate
  # List all other tasks
  invoke --list
  ```

In case you use the recommended VSCode IDE to develop, you'll notice additional
differences:

- New plugins are recommended. It's redundant, but I recommend you to install them.
- Most tasks are removed. Instead, use `invoke` now, which works no matter what editor
  you use. Of course, one of the new recommended extensions adds a command to your
  editor called _Invoke a task_, which runs `invoke` for you.
