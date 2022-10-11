"""Shared template `TestCase` classes and methods for use in jinja2html tests"""

from pathlib import Path
from unittest.case import TestCase


class J2hTestCase(TestCase):
    """Basic template for testing jinja2html"""

    RES_DIR: Path = Path("tests/resources").resolve()  # script is run from the root repo dir
    SAMPLE_PROJECT: Path = RES_DIR / "sample_project"
    SAMPLE_TEMPLATES: Path = SAMPLE_PROJECT / "templates"
