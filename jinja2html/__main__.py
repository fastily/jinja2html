"""jinja2html - friendly generation of websites with jinja2 templates.  Entry point."""

import argparse
import asyncio
import http.server
import json
import logging

import socketserver
import webbrowser

from collections import defaultdict
from functools import partial
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

import websockets

from rich.logging import RichHandler
from watchgod import awatch, Change

from .core import Context, find_acceptable_files, JinjaWatcher, WebsiteManager


sessions = defaultdict(list)

WEBSOCKET_SERVER_PORT = 35729


log = logging.getLogger(__name__)


async def ws_handler(websocket: websockets.WebSocketServerProtocol):
    """Handler managing websocket lifecycle.  Pass this to websockets.serve()

    Arguments:
        websocket {WebSocketServerProtocol} -- Provided by websockets.serve()
        _ {str} -- URL path which was called to create this websocket.  Not used by jinja2html.
    """
    request_content = json.loads(await websocket.recv())

    # initial handshake
    log.debug("recieved message via websocket from a client: %s", request_content)

    if request_content.get("command") == "hello":
        await websocket.send('{"command": "hello", "protocols": ["http://livereload.com/protocols/official-7"], "serverName": "jinja2html"}')
    else:
        log.error("Bad liveserver handshake request from a client: %s", str(request_content))
        return

    request_content = json.loads(await websocket.recv())

    #  sample reply: {'command': 'info', 'plugins': {'less': {'disable': False, 'version': '1.0'}}, 'url': 'http://localhost:8000/ok.html'}
    if request_content.get("command") == "info":
        log.info("New websocket connection estasblished at: %s", request_content.get('url'))
    else:
        log.error("Something went wrong during response from handshake: %s", str(request_content))
        return

    url_path = urlparse(request_content.get('url')).path.lstrip("/")
    sessions[url_path].append(websocket)

    log.debug("added a new websocket, websocket sessions are now %s: ", sessions)

    while True:
        try:
            request_content = json.loads(await websocket.recv())
            log.info("Recieved message from client: %s", request_content)
        except websockets.exceptions.WebSocketException as e:
            log.info("Closing websocket on '%s'", url_path)  # TODO: specifics
            break
        except asyncio.CancelledError:
            log.debug("Recieved cancel in ws_handler.  Doing nothing though.")
            continue

    sessions[url_path].remove(websocket)
    log.debug("removed a dead websocket, websocket sessions are now %s: ", sessions)


async def process_queue(wm: WebsiteManager):
    """Processes task_queue, notifying available clients of changed files, which were added by watchdog handler (MyHandler)"""

    async for changes in awatch(wm.context.input_dir, watcher_cls=JinjaWatcher, watcher_kwargs={"context": wm.context}):
        rebuild: list[Path] = []

        for change, p in changes:

            if change in (Change.added, Change.modified):
                rebuild.append(Path(p))
            else:
                pass  # TODO: deleted files

        wm.process_files(rebuild)

        for p in rebuild:
            p = p.relative_to(wm.context.input_dir)

            message = f'{{"command": "reload", "path": "{p}", "liveCSS": false}}'
            if str(p) in sessions and sessions[str(p)]:
                await asyncio.wait([asyncio.create_task(socket.send(message)) for socket in sessions[str(p)]])

            if p.name == "index.html" and "" in sessions and sessions[""]:
                await asyncio.wait([asyncio.create_task(socket.send(message)) for socket in sessions[""]])


async def ws_server():
    """Creates a websocket server and waits for it to be closed"""
    try:
        log.info("Serving websockets on http://localhost:%d", WEBSOCKET_SERVER_PORT)
        async with websockets.serve(ws_handler, "localhost", WEBSOCKET_SERVER_PORT):
            await asyncio.Future()

    except asyncio.CancelledError:
        log.debug("Received cancel in ws_server.  Doing nothing though.")


async def wss_manager(wm: WebsiteManager):
    """Entry point for asyncio operations in jinja2html"""
    try:
        log.info("Setting up websocket server and process queue...")
        tasks = asyncio.gather(ws_server(), process_queue(wm))
        await tasks
    except asyncio.CancelledError:
        log.debug("Received cancel in wss_manager.  Doing nothing though.")


def _main():
    """Main entry point, runs when this script is invoked directly."""
    cli_parser = argparse.ArgumentParser(description="Render jinja2 templates as html/css/js")
    cli_parser.add_argument("-d", action="store_true", help="enable development mode (live-reload)")
    cli_parser.add_argument("-p", type=int, metavar="port", default=8000, help="serve website on this port")
    cli_parser.add_argument("--ignore", nargs="+", type=Path, metavar="ignored_dir", default=set(), help="directories to ignore")
    args = cli_parser.parse_args()

    c = Context(ignore_list=args.ignore, dev_mode=args.d)
    # c.clean()

    wm = WebsiteManager(c)
    wm.process_files(find_acceptable_files(c))

    if not c.dev_mode:
        return

    log.addHandler(RichHandler(rich_tracebacks=True))
    log.setLevel(logging.INFO)

    socketserver.TCPServer.allow_reuse_address = True  # don't care about OSErrors
    httpd = socketserver.TCPServer(("localhost", args.p), partial(http.server.SimpleHTTPRequestHandler, directory=str(c.output_dir)))
    Thread(target=httpd.serve_forever, daemon=True).start()

    webbrowser.open_new_tab(web_url := f"http://{httpd.server_address[0]}:{httpd.server_address[1]}")
    log.info("Serving website on '%s'", web_url)

    log.info("Watching '%s' for html/js/css changes", c.input_dir)

    try:
        asyncio.run(wss_manager(wm))
    except KeyboardInterrupt:
        print()
        httpd.shutdown()
        log.warning("Keyboard interrupt - bye")


if __name__ == '__main__':
    _main()
