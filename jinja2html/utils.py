"""shared utility methods for jinja2html"""

from pathlib import Path


def _normalized_ext(f: Path) -> str:
    """Convenience method, gets the file extension of `f` in lowercase

    Args:
        f (Path): The file to get the lowercased extension of.

    Returns:
        str: The lowercased extension of `f`, if possible
    """
    return f.suffix.lower()


def is_css_js(f: Path) -> bool:
    """Convenience method, determines whether `f` represents a css/js file.

    Args:
        f (Path): The file to check.

    Returns:
        bool: `True` if `f` is a css/js file.
    """
    return _normalized_ext(f) in (".css", ".js")


def is_html(f: Path) -> bool:
    """Convenience method, determines whether `f` represents an jinja file.

    Args:
        f (Path): The file to check.

    Returns:
        bool: `True` if `f` is a jinja file.
    """
    return _normalized_ext(f) == ".html"
