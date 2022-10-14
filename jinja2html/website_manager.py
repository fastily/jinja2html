"""classes for handling the actual building of the website and filtering of files we're interested in."""

import json
import logging

from collections import deque, Iterable
from os import scandir
from pathlib import Path
from shutil import copy

from bs4 import BeautifulSoup
from watchfiles import Change, DefaultFilter

from .build_context import Context
from .utils import is_css_js, is_html

log = logging.getLogger(__name__)


class WebsiteManager:
    """Methods for rebuilding the output files (the website)"""

    def __init__(self, context: Context) -> None:
        """Initalizer, creates a new `WebsiteManager` with the specified `Context`.

        Args:
            context (Context): The `Context` to use.
        """
        self.context = context

    def find_acceptable_files(self) -> set[Path]:
        """Recursively searches the input directory, according to the input context, for files that should be processed.  Useful for cases when the whole website needs to be rebuilt.

        Returns:
            set[Path]: The files that should be processed.
        """
        l = deque([self.context.input_dir])
        files = set()

        while l:
            with scandir(l.popleft()) as it:
                for entry in map(Path, it):
                    if self.context.is_content_file(entry):
                        files.add(entry)
                    elif self.context.is_content_dir(entry):
                        l.append(entry)

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
                log.debug("copying '%s' into output", f)
                copy(f, output_path)
            elif is_html(f):
                log.debug("building html for '%s'", f)

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

    def __call__(self, change: Change, path: str) -> bool:
        """Gets called by `watchfiles` when it checks if changes to a path should be reported.

        Args:
            change (Change): The kind of `Change` detected
            path (str): The path that was changed.

        Returns:
            bool: `True` if the change should be reported.
        """
        return self.context.is_content_file(path) or self.context.is_content_dir(path) or self.context.is_config_json(path) or self.context.is_template(path, change)
