# How to contribute

<details>
<!-- prettier-ignore-start -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<summary>Table of contents</summary>

- [General Discussion](#general-discussion)
- [Issues](#issues)
- [Propose Changes](#propose-changes)
  - [Set up a Development Environment](#set-up-a-development-environment)
    - [Know our Development Toolkit](#know-our-development-toolkit)
  - [Open a Pull Request](#open-a-pull-request)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- prettier-ignore-end -->
</details>

You should know how to use Github to contribute to this project. To learn, please follow
these tutorials:

- [Introduction to GitHub](https://lab.github.com/githubtraining/introduction-to-github)

Now that you know how to use Github, we just follow the standard process like everybody
else here: issues and pull requests.

## General Discussion

Please make use of [Doodba discussions](https://github.com/Tecnativa/doodba/discussions)
to share knowledge, ideas or make questions.

There's one concrete
[channel for stuff specifically related to this template](https://github.com/Tecnativa/doodba/discussions?discussions_q=category%3A%22Doodba+-+The+template%22).

## Issues

First of all, make sure your problem or suggestion is related to doodba-copier-template.

If that's the case, open an issue in our Github project.
[Read the instructions](https://help.github.com/en/github/managing-your-work-on-github/creating-an-issue)
to know how to do it.

## Propose Changes

### Set up a Development Environment

To hack in this project, you need to set up a development environment. To do that, first
make sure you have installed the essential dependencies:

- [git](https://git-scm.com/)
- [invoke](https://www.pyinvoke.org/)
- [poetry](https://python-poetry.org/)
- [python](https://www.python.org/) 3.6+

Then, execute:

```bash
git clone https://github.com/Tecnativa/doodba-copier-template.git
cd doodba-copier-template
invoke develop
```

🎉 Your development environment is ready! Start hacking.

#### Know our Development Toolkit

Once you did the steps above, it will be good for you to know that our basic building
blocks here are:

- [copier](https://github.com/pykong/copier)
- [poetry](https://python-poetry.org/)
- [pre-commit](https://pre-commit.com/)
- [pytest](https://docs.pytest.org/)

### Open a Pull Request

Follow
[Github's instructions to open a pull request](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request).

After you've done that:

1. We will review it ASAP.
1. "ASAP" could be a long time; remember you don't pay us. 😉
1. If it fits the project, we will possibly ask you to change some things.
1. If it doesn't fit the project, we could reject it. Don't take it bad but maintaining
   stuff in the long term takes time... You can always use your own fork!
