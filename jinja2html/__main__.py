"""jinja2html - friendly generation of websites with jinja2 templates.  Entry point."""

import asyncio
import logging

from argparse import ArgumentParser
from pathlib import Path

from rich.logging import RichHandler

from .build_context import Context
from .website_manager import WebsiteManager
from .web_ui import main_loop


def _main() -> None:
    """Main entry point, runs when this script is invoked directly."""

    cli_parser = ArgumentParser(description="Render jinja2 templates as html/css/js")
    cli_parser.add_argument("-d", action="store_true", help="enable development mode (live-reload)")
    cli_parser.add_argument("-p", type=int, metavar="port", default=8000, help="serve website on this port")
    cli_parser.add_argument("-i", type=Path, metavar="input_dir", default=Path("."), help="The input directory (contianing jinja templates) to use.  Defaults to the current working directory.")
    cli_parser.add_argument("-o", type=Path, metavar="output_dir", default=Path("out"), help="The output directory to write website output files to.  Defaults to ./out")
    cli_parser.add_argument("-t", type=str, metavar="template_dir", default="templates", help="Shared templates directory (relative path only, this must be a subfolder of the input directory).  Defaults to templates")
    cli_parser.add_argument("--debug", action="store_true", help="Enables debug level logging")
    cli_parser.add_argument("--ignore", nargs="+", type=Path, metavar="ignored_dir", default=set(), help="directories to ignore")

    args = cli_parser.parse_args()

    log = logging.getLogger("jinja2html")
    log.addHandler(RichHandler(rich_tracebacks=True))
    log.setLevel(logging.DEBUG if args.debug else logging.INFO)

    (c := Context(args.i, args.o, args.t, args.ignore, args.d)).clean()
    (wm := WebsiteManager(c)).build_files(auto_find=True)

    if not c.dev_mode:
        return

    log.info("Serving website on 'localhost:%d' and watching '%s' for html/js/css changes", args.p, c.input_dir)

    try:
        asyncio.run(main_loop(wm, args.p))
    except KeyboardInterrupt:
        log.info("Keyboard interrupt - bye")


if __name__ == '__main__':
    _main()
