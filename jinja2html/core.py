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

    _FILE_PATTERN = re.compile(r"[^.].+\.(html|htm|css|js)", re.IGNORECASE)

    _NOT_DIR_PATTERN = re.compile(r"(\.|venv_|__pycache)")

    def __init__(self, input_dir: Path = Path("."), output_dir: Path = Path("out"), template_dir: Path = Path("templates"), ignore_list: set[Path] = set(), dev_mode: bool = False) -> None:
        self.input_dir: Path = input_dir.resolve()
        self.output_dir: Path = output_dir.resolve()
        self.template_dir: Path = template_dir.resolve()
        self.ignore_list: set[Path] = {p.resolve() for p in ignore_list} if ignore_list else ignore_list  # TODO: add support for this
        self.dev_mode: bool = dev_mode

        self.config_json = (self.input_dir / "config.json").resolve()
        self.t_env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.input_dir))

    def clean(self) -> None:
        shutil.rmtree(self.output_dir, ignore_errors=True)

        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def should_watch_file(self, entry: DirEntry) -> bool:
        return Context._FILE_PATTERN.match(entry.name) or Path(entry.path) == self.config_json

    def should_watch_dir(self, entry: DirEntry) -> bool:
        return Path(entry.path) != self.output_dir and not Context._NOT_DIR_PATTERN.match(entry.name)


class WebsiteManager:

    def __init__(self, context: Context) -> None:
        self.context = context

    def process_files(self, files: Iterable[Path]) -> None:

        if not files:
            return

        conf = json.loads(self.context.config_json.read_text()) if self.context.config_json.is_file() else {}

        for f in files:
            stub = f.relative_to(self.context.input_dir)
            (output_path := self.context.output_dir / stub).parent.mkdir(parents=True, exist_ok=True)  # create dir structure if it doesn't exist

            if (ext := f.suffix.lower()) in (".js", ".css"):
                shutil.copy(f, output_path)
            elif ext in (".html", ".htm"):
                log.debug("building html for %s", f)

                try:
                    output = self.context.t_env.get_template(str(stub)).render(conf)

                    if self.context.dev_mode:
                        soup = BeautifulSoup(output, "lxml")
                        body_tag = soup.find("body")

                        # add config for livereload
                        script_tag = soup.new_tag("script")
                        script_tag.string = 'window.LiveReloadOptions = {host: "localhost"}'
                        body_tag.append(script_tag)

                        # actually add the script
                        body_tag.append(soup.new_tag("script", src="https://cdnjs.cloudflare.com/ajax/libs/livereload-js/3.3.2/livereload.min.js", integrity="sha512-XO7rFek26Xn8H4HecfAv2CwBbYsJE+RovkwE0nc0kYD+1yJr2OQOOEKSjOsmzE8rTrjP6AoXKFMqReMHj0Pjkw==", crossorigin="anonymous"))
                        output = str(soup)

                    output_path.write_text(output)

                except AttributeError:
                    log.warning("Malformed or non-existent html in '%s', skipping", f)
                except Exception:
                    log.error("Unable to build HTML!", exc_info=True)


class JinjaWatcher(DefaultWatcher):

    def __init__(self, root_path: Union[Path, str] = None, context: Context = Context()) -> None:
        self.context = context

        super().__init__(root_path or context.input_dir)

    def should_watch_file(self, entry: DirEntry) -> bool:
        return self.context.should_watch_file(entry)

    def should_watch_dir(self, entry: DirEntry) -> bool:
        return self.context.should_watch_dir(entry)


def find_acceptable_files(context: Context) -> set[Path]:
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
