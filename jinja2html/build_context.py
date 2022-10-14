"""the central build context and configuration options"""

import logging
import re

from pathlib import Path
from shutil import rmtree
from typing import Union

from jinja2 import Environment, FileSystemLoader
from watchfiles import Change, DefaultFilter

from .utils import is_html


log = logging.getLogger(__name__)


class Context:
    """Collects shared configuration and simple methods for determining which files/directories to watch.  There should only be one instance of this during the program's lifeycle."""

    _FILE_PATTERN = re.compile(r"[^.].*?\.(html|css|js)$", re.IGNORECASE)

    def __init__(self, input_dir: Path = Path("."), output_dir: Path = Path("out"), template_dir: str = "templates", ignore_list: set[Path] = set(), dev_mode: bool = False) -> None:
        """Initializer, creates a new `Context`.  For best results, all `Path` type arguments should be absolute (this is automatically done in the initializer, but if you want to change the properties after initializing, make sure you do this).

        Args:
            input_dir (Path, optional): The directory to watch for changes. Defaults to Path(".").
            output_dir (Path, optional): The directory to save generated files. Defaults to Path("out").
            template_dir (str, optional): The directory containing jinja2 mixin-type templates.  If it exists, this is the name of a folder under `input_dir`. Defaults to "templates".
            ignore_list (set[Path], optional): The set of directories to ignore (will not be watched, even if `input_dir` is a parent folder). Defaults to set().
            dev_mode (bool, optional): Flag which turns on development mode (i.e. livereload server). Defaults to False.
        """
        self.input_dir: Path = input_dir.resolve()
        self.output_dir: Path = output_dir.resolve()
        self.template_dir: Path = self.input_dir / template_dir
        self.dev_mode: bool = dev_mode

        self.ignored_dirs: set[Path] = ({p.resolve() for p in ignore_list} if ignore_list else ignore_list) | {self.output_dir}

        self.config_json = (self.input_dir / "config.json").resolve()
        self.t_env = Environment(loader=FileSystemLoader(self.input_dir))

    def clean(self) -> None:
        """Delete the output directory and regenerate all directories used by jinja2html."""
        rmtree(self.output_dir, ignore_errors=True)

        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def stub_of(self, f: Path) -> Path:
        """Convenience method, gets the path stub of `f` relative to `self.input_dir`.  Useful for determining the path of the file in the output directory (`self.output_dir`).

        Args:
            f (Path): The file `Path` to get an output stub for.

        Returns:
            Path: The output path of `f` relative to `self.input_dir`.
        """
        return f.relative_to(self.input_dir)

    def is_template(self, f: Union[Path, str], change: Change = None) -> bool:
        """Convienience method, determines whether a file is a template (i.e. in the `self.template_dir` directory)

        Args:
            f (Union[Path, str]): The file to check.  Use an absolute `Path` for best results.
            change (Change, optional): The type of `Change` to associate with this check.  Defaults to None.

        Returns:
            bool: `True` if `f` is a template in the `self.template_dir` directory.
        """
        return ((f := _abs_path_of(f)).is_file() or change == Change.deleted) and self.template_dir in f.parents and is_html(f)

    def is_config_json(self, f: Union[Path, str]) -> bool:
        """Convienience method, determines whether `f` is the `config.json` file.

        Args:
            f (Union[Path, str]): The file to check.

        Returns:
            bool: `True` if `f` is the `config.json` file.
        """
        return _abs_path_of(f) == self.config_json

    def is_content_file(self, p: Union[Path, str]) -> bool:
        """Determines whether a file should be watched.

        Args:
            p (Union[Path, str]): The path to the file to check.

        Returns:
            bool: `True` if the file should be watched.
        """
        return bool((p := Path(p)).is_file() and Context._FILE_PATTERN.match(p.name) and self.template_dir not in p.parents)

    def is_content_dir(self, p: Union[Path, str]) -> bool:
        """Determines if `p` is a directory containing jinja content.  Filters out template directories and ignored dirs.

        Args:
            p (Union[Path, str]): The path to check

        Returns:
            bool: `True` if `p` is a content directory.
        """
        return (p := _abs_path_of(p)).is_dir() and \
            p != self.template_dir and self.template_dir not in p.parents and \
            p.name not in DefaultFilter.ignore_dirs and p not in self.ignored_dirs


def _abs_path_of(p: Union[Path, str]) -> Path:
    """Convenience method, determines the absolute path of `p` and returns it as a `Path`

    Args:
        p (Union[Path, str]): The path to convert to an absolute path

    Returns:
        Path: The `p` resolved to an absolute path, as a `Path`
    """
    return Path(p).resolve()
