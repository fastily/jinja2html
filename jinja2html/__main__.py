"""jinja2html - friendly generation of websites with jinja2 templates.  Entry point."""

import argparse
import asyncio
import json
import logging
import socketserver

from collections import defaultdict
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse
from webbrowser import open_new_tab

import websockets

from rich.logging import RichHandler
from watchfiles import awatch, Change

from .core import Context, is_css_js, WebsiteManager


_SESSIONS = defaultdict(list)

_WEBSOCKET_SERVER_PORT = 35729

log = logging.getLogger(__name__)


async def ws_handler(websocket: websockets.WebSocketServerProtocol) -> None:
    """Handler managing an individual websocket's lifecycle, for use with `websockets.serve`

    Args:
        websocket (websockets.WebSocketServerProtocol): The websocket object representing a new websocket connection.
    """
    request_content = json.loads(await websocket.recv())
    log.debug("received message via websocket from a client: %s", request_content)

    if request_content.get("command") == "hello":  # initial handshake
        await websocket.send('{"command": "hello", "protocols": ["http://livereload.com/protocols/official-7"], "serverName": "jinja2html"}')
    else:
        log.error("Bad liveserver handshake request from a client: %s", request_content)
        return

    request_content = json.loads(await websocket.recv())

    #  sample reply: {'command': 'info', 'plugins': {'less': {'disable': False, 'version': '1.0'}}, 'url': 'http://localhost:8000/ok.html'}
    if request_content.get("command") == "info":
        log.info("New websocket connection estasblished at: %s", request_content.get('url'))
    else:
        log.error("Something went wrong during response from handshake: %s", request_content)
        return

    url_path = urlparse(request_content.get('url')).path.lstrip("/")
    _SESSIONS[url_path].append(websocket)

    log.debug("added a new websocket, websocket sessions are now %s: ", _SESSIONS)

    try:
        async for message in websocket:
            log.info("received message from client: %s", message)
    except websockets.exceptions.WebSocketException as e:
        log.info("Closing websocket on '%s'", url_path)  # TODO: specifics
    except asyncio.CancelledError:
        log.debug("received cancel in ws_handler.  Doing nothing though.")

    _SESSIONS[url_path].remove(websocket)
    log.debug("removed a dead websocket, websocket sessions are now %s: ", _SESSIONS)


async def changed_files_handler(wm: WebsiteManager) -> None:
    """Detects and handles updates to watched html/js/css files.   Specifically, rebuild changed website files and notify websocket clients of changes.

    Args:
        wm (WebsiteManager):  The WebsiteManager to associate with this asyncio loop
    """
    async for changes in awatch(wm.context.input_dir, watch_filter=wm.jinja_filter):
        l: set[Path] = set()
        build_all = notify_all = False

        for change, p in changes:
            p = Path(p)
            if wm.context.is_template(p) or wm.context.is_config_json(p):
                l = wm.find_acceptable_files()
                build_all = True
                break
            elif change in (Change.added, Change.modified):
                l.add(p)
                if is_css_js(p):
                    notify_all = True
            else:
                (wm.context.output_dir / wm.context.stub_of(p)).unlink(True)

        wm.build_files(l)

        if notify_all and not build_all:
            l = wm.find_acceptable_files()

        for p in l:
            stub = str(wm.context.stub_of(p))
            message = f'{{"command": "reload", "path": "{stub}", "liveCSS": false}}'

            if _SESSIONS.get(stub):
                await asyncio.wait([asyncio.create_task(socket.send(message)) for socket in _SESSIONS[stub]])

            if p.name == "index.html" and _SESSIONS.get(""):
                await asyncio.wait([asyncio.create_task(socket.send(message)) for socket in _SESSIONS[""]])


async def ws_server() -> None:
    """Creates a websocket server and waits for it to be closed"""
    try:
        log.info("Serving websockets on http://localhost:%d", _WEBSOCKET_SERVER_PORT)
        async with websockets.serve(ws_handler, "localhost", _WEBSOCKET_SERVER_PORT):
            await asyncio.Future()

    except asyncio.CancelledError:
        log.debug("Received cancel in ws_server.  Doing nothing though.")


async def main_loop(wm: WebsiteManager) -> None:
    """Entry point for asyncio operations in jinja2html

    Args:
        wm (WebsiteManager): The WebsiteManager to associate with this asyncio loop
    """
    try:
        log.info("Setting up websocket server and process queue...")
        await asyncio.gather(ws_server(), changed_files_handler(wm))
    except asyncio.CancelledError:
        log.debug("Received cancel in wss_manager.  Doing nothing though.")


def _main() -> None:
    """Main entry point, runs when this script is invoked directly."""
    cli_parser = argparse.ArgumentParser(description="Render jinja2 templates as html/css/js")
    cli_parser.add_argument("-d", action="store_true", help="enable development mode (live-reload)")
    cli_parser.add_argument("-p", type=int, metavar="port", default=8000, help="serve website on this port")
    cli_parser.add_argument("-i", type=Path, metavar="input_dir", default=Path("."), help="The input directory (contianing jinja templates) to use.  Defaults to the current working directory.")
    cli_parser.add_argument("-o", type=Path, metavar="output_dir", default=Path("out"), help="The output directory to write website output files to.  Defaults to ./out")
    cli_parser.add_argument("-t", type=str, metavar="template_dir", default="templates", help="Shared templates directory (relative path only, this must be a subfolder of the input directory).  Defaults to templates")
    cli_parser.add_argument("--blacklist", nargs="+", type=Path, metavar="ignored_dir", default=set(), help="directories to ignore")

    args = cli_parser.parse_args()

    (c := Context(args.i, args.o, args.t, args.blacklist, args.d)).clean()
    (wm := WebsiteManager(c)).build_files(auto_find=True)

    if not c.dev_mode:
        return

    log.addHandler(RichHandler(rich_tracebacks=True))
    log.setLevel(logging.INFO)

    socketserver.TCPServer.allow_reuse_address = True  # ward off OSErrors
    Thread(target=(httpd := socketserver.TCPServer(("localhost", args.p), partial(SimpleHTTPRequestHandler, directory=str(c.output_dir)))).serve_forever).start()

    open_new_tab(web_url := f"http://{httpd.server_address[0]}:{httpd.server_address[1]}")
    log.info("Serving website on '%s' and watching '%s' for html/js/css changes", web_url, c.input_dir)

    try:
        asyncio.run(main_loop(wm))
    except KeyboardInterrupt:
        print()
        httpd.shutdown()
        log.warning("Keyboard interrupt - bye")


if __name__ == '__main__':
    _main()
