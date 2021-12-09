"""Tests for core modules of jinja2html"""

from filecmp import dircmp
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.case import TestCase

from jinja2html.core import Context, find_acceptable_files, WebsiteManager


_RES_DIR = Path("tests/resources").resolve()  # script is run from the root repo dir
_SAMPLE_PROJECT = _RES_DIR / "sample_project"
_SAMPLE_TEMPLATES = _SAMPLE_PROJECT / "templates"


class TestCore(TestCase):
    """Test global methods and classes in core"""

    def test_find_acceptable_files(self):
        expected = {_SAMPLE_PROJECT / s for s in ("config.json", "content1.html", "content2.html", "index.html", "shared.css", "shared.js")}
        with TemporaryDirectory() as tempdir:
            self.assertSetEqual(expected, find_acceptable_files(Context(_SAMPLE_PROJECT, Path(tempdir), _SAMPLE_TEMPLATES)))

    def test_process_files(self):
        with TemporaryDirectory() as tempdir:
            WebsiteManager(c := Context(_SAMPLE_PROJECT, Path(tempdir), _SAMPLE_TEMPLATES)).process_files(find_acceptable_files(c))

            self.assertFalse(dircmp(_RES_DIR / "expected_output", tempdir).diff_files)

    def test_sanity(self):
        with TemporaryDirectory() as tempdir:
            c = Context(_SAMPLE_PROJECT, Path(tempdir), _SAMPLE_TEMPLATES)

            self.assertEqual(Path("index.html"), c.stub_of(_SAMPLE_PROJECT / "index.html"))
            self.assertEqual(Path("shared.js"), c.stub_of(_SAMPLE_PROJECT / "shared.js"))

            self.assertTrue(c.is_template(_SAMPLE_TEMPLATES / "base.html"))
            self.assertFalse(c.is_template(_SAMPLE_TEMPLATES / "lol.js"))
            self.assertFalse(c.is_template(_SAMPLE_PROJECT / "base.html"))

            self.assertTrue(c.is_config_json(_SAMPLE_PROJECT / "config.json"))
            self.assertFalse(c.is_config_json(_SAMPLE_PROJECT / "sus.json"))
            self.assertFalse(c.is_config_json(_SAMPLE_TEMPLATES / "config.json"))
            self.assertFalse(c.is_config_json(_SAMPLE_PROJECT / "ok.html"))
