"""core classes and utilities for jinja2html"""

import json
import logging
import re
import shutil

from collections import deque, Iterable
from os import scandir
from pathlib import Path

import jinja2

from bs4 import BeautifulSoup
from watchfiles import Change, DefaultFilter


log = logging.getLogger(__name__)

_FILE_PATTERN = re.compile(r"[^.].+\.(html|htm|css|js)", re.IGNORECASE)

# _NOT_DIR_PATTERN = re.compile(r"(\.|venv_|__pycache)")


class Context:
    """Collects shared configuration and simple methods for determining which files/directories to watch.  There should only be one instance of this during the program's lifeycle."""

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

    def is_template(self, f: Path) -> bool:
        """Convienience method, determines whether a file is a template (i.e. in the `self.template_dir` directory)

        Args:
            f (Path): The file to check.  Use an absolute `Path` for best results.

        Returns:
            bool: `True` if `f` is a template in the `self.template_dir` directory.
        """
        return self.template_dir in f.parents and is_html(f)

    def is_config_json(self, f: Path) -> bool:
        """Convienience method, determines whether `f` is the `config.json` file.

        Args:
            f (Path): The file to check.  Use an absolute `Path` for best results.

        Returns:
            bool: `True` if `f` is the `config.json` file.
        """
        return f == self.config_json

    def should_watch_file(self, p: str) -> bool:
        """Determines whether a file should be watched.

        Args:
            entry (str): The path to the file to check.  Must be a full path.

        Returns:
            bool: `True` if the file should be watched.
        """
        return _FILE_PATTERN.match(p) or self.is_config_json(Path(p))


class WebsiteManager:
    """Methods for rebuilding the output files (the website)"""

    def __init__(self, context: Context) -> None:
        """Initalizer, creates a new `WebsiteManager` with the specified `Context`.

        Args:
            context (Context): The `Context` to use.
        """
        self.context = context
        self.jinja_filter = JinjaFilter(context)

    def find_acceptable_files(self) -> set[Path]:
        """Recursively searches the input directory, according to the input context, for files that should be processed.  Useful for cases when the whole website needs to be rebuilt.

        Returns:
            set[Path]: The files that should be processed.
        """
        l = deque([self.context.input_dir])
        files = set()

        while l:
            with scandir(l.popleft()) as it:
                for entry in it:
                    entry_as_path = Path(entry)

                    if entry.is_file():
                        if self.context.should_watch_file(entry.path):
                            files.add(entry_as_path)
                    else:  # is_dir()
                        if entry_as_path not in self.context.ignore_list and entry_as_path != self.context.template_dir and self.jinja_filter(Change.added, entry.path):
                            l.append(entry.path)

        return files

    def build_files(self, files: Iterable[Path] = (), auto_find: bool = False) -> None:
        """Processes the specified files and saves them to the output directory.  Only acts on jinja/js/css files, everything else will be ignored.  If `auto_find` is `True`, then this method automatically rebuilds all eligible files in the input directory.

        Args:
            files (Iterable[Path], optional): The files to generate website files for.  Ignored if `auto_find` is `True`. Defaults to ().
            auto_find (bool, optional): Set `True` to automatically rebuild all eligible files in the input directory.  Defaults to False.
        """
        if auto_find:
            files = self.find_acceptable_files()
        elif not files:
            return

        conf = json.loads(self.context.config_json.read_text()) if self.context.config_json.is_file() else {}

        for f in files:
            (output_path := self.context.output_dir / (stub := self.context.stub_of(f))).parent.mkdir(parents=True, exist_ok=True)  # create dir structure if it doesn't exist

            if is_css_js(f):
                shutil.copy(f, output_path)
            elif is_html(f):
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
                        body_tag.append(soup.new_tag("script", src="https://cdnjs.cloudflare.com/ajax/libs/livereload-js/3.4.1/livereload.min.js", integrity="sha512-rclIrxzYHDmi28xeUES7WqX493chZ4LFEdbjMAUYiosJlKqham0ZujKU539fTFnZywE0c76XIRl9pLJ05OJPKA==", crossorigin="anonymous"))
                        output = str(soup)

                    output_path.write_text(output)

                except AttributeError:
                    log.warning("Malformed or non-existent html in '%s', skipping", f)
                except Exception:
                    log.error("Unable to build HTML!", exc_info=True)


class JinjaFilter(DefaultFilter):
    """A `DefaultFilter` subclass which only finds jinja2html-related files, for use `watchfiles`."""

    def __init__(self, context: Context) -> None:
        """Initializer, creates a new `JinjaFilter`.

        Args:
            context (Context): The `Context` to use.
        """
        self.context = context
        super().__init__(ignore_paths=tuple(context.ignore_list))

    def __call__(self, change: Change, path: str) -> bool:
        """Gets called by `watchfiles` when it checks if changes to a path should be reported.

        Args:
            change (Change): The kind of `Change` detected
            path (str): The path that was changed.

        Returns:
            bool: `True` if the change should be reported.
        """
        return self.context.should_watch_file(path) and super().__call__(change, path)


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
