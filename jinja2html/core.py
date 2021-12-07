"""core classes and utilities for jinja2html"""

import json
import logging
import re
import shutil

from collections import deque, Iterable
from os import DirEntry, scandir
from pathlib import Path
from typing import Union

import jinja2

from bs4 import BeautifulSoup
from watchgod import DefaultWatcher


log = logging.getLogger(__name__)


class Context:
    """Collects shared configuration and simple methods for determining which files/directories to watch.  There should only be one instance of this during the program's lifeycle."""

    _FILE_PATTERN = re.compile(r"[^.].+\.(html|htm|css|js)", re.IGNORECASE)

    _NOT_DIR_PATTERN = re.compile(r"(\.|venv_|__pycache)")

    def __init__(self, input_dir: Path = Path("."), output_dir: Path = Path("out"), template_dir: Path = Path("./templates"), ignore_list: set[Path] = set(), dev_mode: bool = False) -> None:
        """Initializer, creates a new `Context`.  For best results, all `Path` type arguments should be absolute (this is automatically done in the initializer, but if you want to change the properties after initializing, make sure you do this).

        Args:
            input_dir (Path, optional): The directory to watch for changes. Defaults to Path(".").
            output_dir (Path, optional): The directory to save generated files. Defaults to Path("out").
            template_dir (Path, optional): The directory containing jinja2 mixin-type templates. Defaults to Path("./templates").
            ignore_list (set[Path], optional): The set of directories to ignore (will not be watched, even if `input_dir` is a parent folder). Defaults to set().
            dev_mode (bool, optional): Flag which turns on development mode (i.e. livereload server). Defaults to False.
        """
        self.input_dir: Path = input_dir.resolve()
        self.output_dir: Path = output_dir.resolve()
        self.template_dir: Path = template_dir.resolve()
        self.dev_mode: bool = dev_mode

        self.ignore_list: set[Path] = {p.resolve() for p in ignore_list} if ignore_list else ignore_list
        self.ignore_list.add(self.output_dir)

        self.config_json = (self.input_dir / "config.json").resolve()
        self.t_env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.input_dir))

    def clean(self) -> None:
        """Delete the output directory and regenerate all directories used by jinja2html."""
        shutil.rmtree(self.output_dir, ignore_errors=True)

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

    def should_watch_file(self, entry: DirEntry) -> bool:
        """Determines whether a file should be watched.  For use with the output of `os.scandir`

        Args:
            entry (DirEntry): The file to check.

        Returns:
            bool: `True` if the file should be watched.
        """
        return Context._FILE_PATTERN.match(entry.name) or Path(entry.path) == self.config_json

    def should_watch_dir(self, entry: DirEntry) -> bool:
        """Determines whether a directory should be watched.  For use with the output of `os.scandir`

        Args:
            entry (DirEntry): The directory to check.

        Returns:
            bool: `True` if the directory should be watched.
        """
        return Path(entry.path) not in self.ignore_list and not Context._NOT_DIR_PATTERN.match(entry.name)


class WebsiteManager:
    """Methods for rebuilding the output files (the website)"""

    def __init__(self, context: Context) -> None:
        """Initalizer, creates a new `WebsiteManager` with the specified `Context`.

        Args:
            context (Context): The `Context` to use.
        """
        self.context = context

    def process_files(self, files: Iterable[Path]) -> None:
        """Processes the specified files and saves them to the output directory.  Only acts on html/js/css files, everything else will be ignored.

        Args:
            files (Iterable[Path]): The files to generate website files for.
        """
        if not files:
            return

        conf = json.loads(self.context.config_json.read_text()) if self.context.config_json.is_file() else {}

        for f in files:
            (output_path := self.context.output_dir / (stub := self.context.stub_of(f))).parent.mkdir(parents=True, exist_ok=True)  # create dir structure if it doesn't exist

            if (ext := f.suffix.lower()) in (".js", ".css"):
                shutil.copy(f, output_path)
            elif ext in (".html", ".htm"):
                log.debug("building html for %s", f)

                try:
                    output = self.context.t_env.get_template(str(stub)).render(conf)

                    if self.context.dev_mode:
                        soup = BeautifulSoup(output, "lxml")
                        body_tag = soup.find("body")

                        # add livereload config
                        script_tag = soup.new_tag("script")
                        script_tag.string = 'window.LiveReloadOptions = {host: "localhost"}'
                        body_tag.append(script_tag)

                        # add livereload script
                        body_tag.append(soup.new_tag("script", src="https://cdnjs.cloudflare.com/ajax/libs/livereload-js/3.3.2/livereload.min.js", integrity="sha512-XO7rFek26Xn8H4HecfAv2CwBbYsJE+RovkwE0nc0kYD+1yJr2OQOOEKSjOsmzE8rTrjP6AoXKFMqReMHj0Pjkw==", crossorigin="anonymous"))
                        output = str(soup)

                    output_path.write_text(output)

                except AttributeError:
                    log.warning("Malformed or non-existent html in '%s', skipping", f)
                except Exception:
                    log.error("Unable to build HTML!", exc_info=True)


class JinjaWatcher(DefaultWatcher):
    """An `AllWatcher` subclass for use with `watchgod`"""

    def __init__(self, root_path: Union[Path, str] = None, context: Context = Context()) -> None:
        """Initializer, creates a new `JinjaWatcher`.

        Args:
            root_path (Union[Path, str], optional): The root path (input) directory to watch. Defaults to None.
            context (Context, optional): The `Context` to use. Defaults to Context().
        """
        self.context = context

        super().__init__(root_path or context.input_dir)

    def should_watch_file(self, entry: DirEntry) -> bool:
        """Determines whether a file should be watched.

        Args:
            entry (DirEntry): The file to check.

        Returns:
            bool: `True` if the file should be watched.
        """
        return self.context.should_watch_file(entry)

    def should_watch_dir(self, entry: DirEntry) -> bool:
        """Determines whether a directory should be watched.

        Args:
            entry (DirEntry): The directory to check.

        Returns:
            bool: `True` if the directory should be watched.
        """
        return self.context.should_watch_dir(entry)


def find_acceptable_files(context: Context) -> set[Path]:
    """Recursively searches the input directory in `context` for files that should be processed.  Useful for cases when the whole website needs to be rebuilt.

    Args:
        context (Context): The context to use.

    Returns:
        set[Path]: The files that should be processed.
    """
    l = deque([context.input_dir])
    files = set()

    while l:
        with scandir(l.popleft()) as it:
            for entry in it:
                if entry.is_file():
                    if context.should_watch_file(entry):
                        files.add(Path(entry.path))
                else:  # is_dir()
                    if context.should_watch_dir(entry) and Path(entry.path) != context.template_dir:
                        l.append(entry.path)

    return files
