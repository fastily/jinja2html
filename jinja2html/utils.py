"""shared utility methods for jinja2html"""

from pathlib import Path


def _is_ext(f: Path, ext: tuple[str]) -> bool:
    """Determines whether a file has one of the specified extension(s).

    Args:
        f (Path): The file to check.
        ext (tuple[str]): The extension(s) to check for.  These should be lower case.

    Returns:
        bool: `True` if `f` has an extension in `ext`.
    """
    return f.suffix.lower() in ext


def is_css_js(f: Path) -> bool:
    """Convenience method, determines whether `f` represents a css/js file.

    Args:
        f (Path): The file to check.

    Returns:
        bool: `True` if `f` is a css/js file.
    """
    return _is_ext(f, (".css", ".js"))


def is_html(f: Path) -> bool:
    """Convenience method, determines whether `f` represents an jinja file.

    Args:
        f (Path): The file to check.

    Returns:
        bool: `True` if `f` is a jinja file.
    """
    return _is_ext(f, (".html", ".htm", ".jinja"))
