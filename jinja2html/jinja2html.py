"""main entry point for jinja2html"""
import argparse
import glob
import json
import os
from pathlib import Path
import shutil
import time

import livereload
import jinja2

t_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."), autoescape=True)


def build(path, dev=True):
    """Builds the jinja template at the specified path

    Arguments:
        path {str} -- path to the jinja file to build as html

    Keyword Arguments:
        dev {bool} -- set True to enable development mode (injection of livereload js) (default: {True})
    """
    if Path("config.json").is_file():
        with open("config.json") as json_file:
            context = json.load(json_file)
    else:
        context = {}

    output = t_env.get_template(path).render(context)
    # if dev:
    #     try:
    #         soup = BeautifulSoup(output, "lxml")
    #         body_tag = soup.find("body")

    #         # add config for liveReload
    #         script_tag = soup.new_tag("script")
    #         script_tag.string = 'window.LiveReloadOptions = {host: "localhost"}'
    #         body_tag.append(script_tag)

    #         # actually add the script
    #         body_tag.append(soup.new_tag("script", src="https://cdn.jsdelivr.net/npm/livereload-js@3.2.1/dist/livereload.min.js",
    #                                      integrity="sha256-Tm7IcDz9uE2N6RbJ0yeZiLbQRSrtMMMhWEFyG5QD8DI=", crossorigin="anonymous"))
    #         output = soup.prettify()
    #     except AttributeError:
    #         print(f"WARNING: Malformed or non-existent html in '{path}'.  Doing nothing.")

    with open(f"out/{path}", "w") as f:
        f.write(output)


class BuildManager():
    """Manages jinja builds, used only in development mode"""

    def __init__(self):
        """constructor, creates a new BuildManager"""
        self.files = {} # path : last_modified

    def build_changed(self):
        """Should be run whenever a jinja file in the current directory changes.  Finds files which have been modified since this method was last run and rebuilds the jinja files"""
        for f in glob.glob("*.html"):
            if f in self.files:
                last_modified = os.path.getmtime(f)
                if last_modified > self.files[f]:
                    build(f)
                    self.files[f] = last_modified
            else:
                build(f)
                self.files[f] = time.time()

    def build_all(self):
        """Force rebuild of all jinja files in the current directory."""
        for f in glob.glob("*.html"):
            build(f)

        self.build_css()

    def build_css(self):
        """Copy changed CSS into the out folder"""
        for f in glob.glob("*.css"):
            if f in self.files:
                last_modified = os.path.getmtime(f)
                if last_modified > self.files[f]:
                    shutil.copy(f, "out")
                    self.files[f] = last_modified
            else:
                shutil.copy(f, "out")
                self.files[f] = time.time()

def main():
    """Main driver, runs if this file was explicitly executed."""

    cli_parser = argparse.ArgumentParser(description="Renders jinja2 templates as html")
    cli_parser.add_argument("--generate", action='store_true', help="cause all jinja2 files in the current directory to be rendered for prod")
    args = cli_parser.parse_args()

    # setup dev folders
    Path("out").mkdir(parents=True, exist_ok=True)
    Path("templates").mkdir(parents=True, exist_ok=True)

    # if this is for prod, do it now
    if args.generate:
        for f in glob.glob("out/*.html"):
            os.remove(f)

        for f in glob.glob("*.html"):
            build(f, False)
        return

    # set up for dev mode
    build_manager = BuildManager()

    server = livereload.Server()
    server.watch("*.html", build_manager.build_changed)
    server.watch("*.css", build_manager.build_css)
    server.watch("templates/*.html", build_manager.build_all)
    server.watch("config.json", build_manager.build_all)

    build_manager.build_all()

    server.serve(root='out', open_url_delay=1)


if __name__ == '__main__':
    main()
