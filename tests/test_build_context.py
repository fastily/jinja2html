from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2html.build_context import Context

from .base import J2hTestCase


class TestContext(J2hTestCase):
    """Test methods supporting the build context"""

    def test_is_stub_of(self):
        with TemporaryDirectory() as tempdir:
            c = Context(self.SAMPLE_PROJECT, Path(tempdir))

            self.assertEqual(Path("index.html"), c.stub_of(self.SAMPLE_PROJECT / "index.html"))
            self.assertEqual(Path("sub/index.html"), c.stub_of(self.SAMPLE_PROJECT / "sub/index.html"))
            self.assertEqual(Path("shared.js"), c.stub_of(self.SAMPLE_PROJECT / "shared.js"))

    def test_is_some_content(self):
        with TemporaryDirectory() as tempdir:
            c = Context(self.SAMPLE_PROJECT, Path(tempdir))

            self.assertTrue(c.is_template(self.SAMPLE_TEMPLATES / "base.html"))
            self.assertFalse(c.is_template(self.SAMPLE_TEMPLATES / "does-not-exist.html"))
            self.assertFalse(c.is_template(self.SAMPLE_TEMPLATES / "lol.js"))
            self.assertFalse(c.is_template(self.SAMPLE_PROJECT / "base.html"))
            self.assertFalse(c.is_template(self.SAMPLE_PROJECT / "index.html"))

            self.assertTrue(c.is_config_json(self.SAMPLE_PROJECT / "config.json"))
            self.assertFalse(c.is_config_json(self.SAMPLE_PROJECT / "config.js"))
            self.assertFalse(c.is_config_json(self.SAMPLE_PROJECT / "sus.json"))
            self.assertFalse(c.is_config_json(self.SAMPLE_TEMPLATES / "config.json"))
            self.assertFalse(c.is_config_json(self.SAMPLE_PROJECT / "ok.html"))

            self.assertTrue(c.is_content_file(self.SAMPLE_PROJECT / "index.html"))
            self.assertTrue(c.is_content_file(self.SAMPLE_PROJECT / "content2.html"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "does-not-exist.js"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "a.css"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "config.js"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "sub"))
            self.assertFalse(c.is_content_file(self.SAMPLE_TEMPLATES / "base.html"))

            self.assertTrue(c.is_content_dir(self.SAMPLE_PROJECT / "sub"))
            self.assertFalse(c.is_content_dir(self.SAMPLE_PROJECT / "config.json"))
            self.assertFalse(c.is_content_dir(self.SAMPLE_PROJECT / "foobar"))

    def test_ignore(self):
        with TemporaryDirectory() as tempdir:
            c = Context(self.SAMPLE_PROJECT, Path(tempdir), ignore_list={self.SAMPLE_PROJECT / "sub"})

            self.assertTrue(c.is_content_file(self.SAMPLE_PROJECT / "index.html"))
            self.assertTrue(c.is_content_file(self.SAMPLE_PROJECT / "content2.html"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "does-not-exist.js"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "a.css"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "config.js"))
            self.assertFalse(c.is_content_file(self.SAMPLE_PROJECT / "sub"))
            self.assertFalse(c.is_content_file(self.SAMPLE_TEMPLATES / "base.html"))

            self.assertFalse(c.is_content_dir(self.SAMPLE_PROJECT / "sub"))
            self.assertFalse(c.is_content_dir(self.SAMPLE_PROJECT / "config.json"))
            self.assertFalse(c.is_content_dir(self.SAMPLE_PROJECT / "foobar"))
