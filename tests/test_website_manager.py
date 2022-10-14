"""Tests for core modules of jinja2html"""

from filecmp import dircmp
from pathlib import Path
from tempfile import TemporaryDirectory

from watchfiles import Change

from jinja2html.build_context import Context
from jinja2html.website_manager import JinjaFilter, WebsiteManager

from .base import J2hTestCase


class TestWebsiteManager(J2hTestCase):
    """Test global methods and classes in core"""

    def test_find_acceptable_files(self):
        with TemporaryDirectory() as tempdir:
            self.assertSetEqual({self.SAMPLE_PROJECT / s for s in ("content1.html", "content2.html", "index.html", "sub/index.html", "shared.css", "shared.js")},
                                WebsiteManager(Context(self.SAMPLE_PROJECT, Path(tempdir))).find_acceptable_files())

    def test_build_files(self):
        with TemporaryDirectory() as tempdir:
            WebsiteManager(Context(self.SAMPLE_PROJECT, Path(tempdir))).build_files(auto_find=True)

            self.assertFalse(dircmp(self.RES_DIR / "expected_output", tempdir).diff_files)


class TestJinjaFilter(J2hTestCase):

    def test_call(self):
        with TemporaryDirectory() as tempdir:
            jf = JinjaFilter(Context(self.SAMPLE_PROJECT, Path(tempdir)))

            self.assertTrue(jf(Change.modified, str(self.SAMPLE_TEMPLATES / "base.html")))
            self.assertTrue(jf(Change.deleted, str(self.SAMPLE_TEMPLATES / "a.html")))
            self.assertTrue(jf(Change.deleted, str(self.SAMPLE_TEMPLATES / "deleted.html")))
            self.assertFalse(jf(Change.deleted, str(self.SAMPLE_TEMPLATES / "x.css")))

            self.assertTrue(jf(Change.modified, str(self.SAMPLE_PROJECT / "index.html")))
            self.assertTrue(jf(Change.modified, str(self.SAMPLE_PROJECT / "shared.css")))
            self.assertFalse(jf(Change.deleted, str(self.SAMPLE_PROJECT / "a.html")))  # ignore deleted content files

            self.assertTrue(jf(Change.added, str(self.SAMPLE_PROJECT / "sub")))
            self.assertFalse(jf(Change.deleted, str(self.SAMPLE_PROJECT / "nothere")))  # ignore deleted content dirs

            self.assertTrue(jf(Change.modified, str(self.SAMPLE_PROJECT / "config.json")))
            self.assertTrue(jf(Change.deleted, str(self.SAMPLE_PROJECT / "config.json")))

            self.assertFalse(jf(Change.modified, str(self.SAMPLE_PROJECT / "foobar.txt")))
            self.assertFalse(jf(Change.deleted, str(self.SAMPLE_PROJECT / "foobar.txt")))
            self.assertFalse(jf(Change.deleted, str(self.SAMPLE_TEMPLATES / "meh.svg")))
