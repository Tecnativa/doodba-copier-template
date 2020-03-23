"""Template migration scripts.

This file is executed through invoke by copier when updating child projects.
"""
import shutil
from pathlib import Path

from invoke import task


@task
def from_doodba_scaffolding_to_copier(c):
    print("Removing remaining garbage from doodba-scaffolding.")
    shutil.rmtree(Path(".vscode", "doodba"), ignore_errors=True)
    Path(".travis.yml").unlink()
    Path(".vscode", "doodbasetup.py").unlink()
    Path("odoo", "custom", "src", "private", ".empty").unlink()
