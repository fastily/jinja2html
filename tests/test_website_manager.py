"""Tests for core modules of jinja2html"""

from filecmp import dircmp
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2html.build_context import Context
from jinja2html.website_manager import WebsiteManager

from .base import J2hTestCase


class TestWebsiteManager(J2hTestCase):
    """Test global methods and classes in core"""

    def test_find_acceptable_files(self):
        with TemporaryDirectory() as tempdir:
            self.assertSetEqual({self.SAMPLE_PROJECT / s for s in ("content1.html", "content2.html", "index.html", "sub/index.html", "shared.css", "shared.js")},
                                WebsiteManager(Context(self.SAMPLE_PROJECT, Path(tempdir))).find_acceptable_files())

    def test_process_files(self):
        with TemporaryDirectory() as tempdir:
            WebsiteManager(Context(self.SAMPLE_PROJECT, Path(tempdir))).build_files(auto_find=True)

            self.assertFalse(dircmp(self.RES_DIR / "expected_output", tempdir).diff_files)
