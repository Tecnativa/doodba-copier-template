# Migrating From Doodba Scaffolding

Welcome to the migration guide for previous
[doodba-scaffolding](https://github.com/Tecnativa/doodba-scaffolding) users.

I know, I know... you are used to do `git pull scaffolding master` to update your
templates, and now you wonder why now all is more complicated... Let me explain.

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

```bash
# First, update your downstream scaffolding to latest upstream commit
cd ~/path/to/your/downstream/scaffolding
git remote add scaffolding https://github.com/Tecnativa/doodba-scaffolding.git
git pull scaffolding master
# Now you might have conflicts... solve them and commit
solve-my-conflicts-magically # Tell me if you find this command! 😂
git add .
git commit
# Remove the scaffolding remote, you'll never need it again
git remote rm scaffolding
```

OK, you're ready to use copier for the first time, so make sure you installed all you
need (instructions in README), and continue:

```bash
copier update
```

Copier will ask you a lot of questions. **Your answers must match what you already have
in your scaffolding**, or otherwise the update could be problematic.

After finishing, you will notice some important differences:

- A new `.copier-answers.yml` file has been created, with all your answers. It is
  important that you don't touch this file manually and add it to your next commit,
  because it will make further updates work as expected.
- You have a lot of new configs for linters and formatters, including the almighty
  `.pre-commit-config.yaml` file. Execute `pre-commit install` to benefit from its
  features, your code will look awesome now!
- YAML files are now indented with 2 spaces, which is the most readable style for that
  format.
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
