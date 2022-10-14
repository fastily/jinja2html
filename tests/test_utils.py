from pathlib import Path
from unittest.case import TestCase

from jinja2html.utils import is_css_js, is_html


class TestContext(TestCase):
    """Test methods supporting the build context"""

    def test_is_css_js(self):
        self.assertTrue(is_css_js(Path("a/b/c/test.js")))
        self.assertTrue(is_css_js(Path("a.css")))
        self.assertFalse(is_css_js(Path("index.html")))
        self.assertFalse(is_css_js(Path("config.json")))
        self.assertFalse(is_css_js(Path("x/y/z/index.json")))
        self.assertFalse(is_css_js(Path("x.png")))

    def test_is_html(self):
        self.assertTrue(is_html(Path("index.html")))
        self.assertTrue(is_html(Path("sub/index.html")))
        self.assertFalse(is_html(Path("a/b/c/test.js")))
        self.assertFalse(is_html(Path("a.css")))
        self.assertFalse(is_html(Path("config.json")))
        self.assertFalse(is_html(Path("x/y/z/index.json")))
        self.assertFalse(is_html(Path("x.png")))
