#!/usr/bin/env python
"""jinja2html - friendly generation of websites with jinja2 templates.  Main class and entry point."""

import argparse
import asyncio
import http.server
import json
import logging
import shutil
import socketserver
import webbrowser

from collections import defaultdict
from functools import partial
from pathlib import Path
from queue import Queue
from threading import Thread
from urllib.parse import urlparse

import jinja2
import websockets

from bs4 import BeautifulSoup
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer


sessions = defaultdict(list)

task_queue = Queue()

STATIC_SERVER_PORT = 8000

WEBSOCKET_SERVER_PORT = 35729

STATIC_SERVER_ROOT = Path("out")

JINJA_WATCH_PATH = Path(".")

JINJA_TEMPLATE_DIR = Path("templates")

t_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(JINJA_WATCH_PATH)))


async def ws_handler(websocket, path):
    """Handler managing websocket lifecycle.  Pass this to websockets.serve()

    Arguments:
        websocket {WebSocketServerProtocol} -- Provided by websockets.serve()
        path {str} -- URL path which was called to create this websocket.  Not used by jinja2html.
    """
    request_content = json.loads(await websocket.recv())

    # initial handshake
    logging.debug("recieved message via websocket from a client: %s", str(request_content))

    if(request_content.get("command") == "hello"):
        await websocket.send('{"command": "hello", "protocols": ["http://livereload.com/protocols/official-7"], "serverName": "jinja2html"}')
    else:
        logging.error("Bad liveserver handshake request from a client: %s", str(request_content))
        return

    request_content = json.loads(await websocket.recv())

    #  sample reply: {'command': 'info', 'plugins': {'less': {'disable': False, 'version': '1.0'}}, 'url': 'http://localhost:8000/ok.html'}
    if(request_content.get("command") == "info"):
        logging.info("New websocket connection estasblished at: %s", request_content.get('url'))
    else:
        logging.error("Something went wrong during response from handshake: %s", str(request_content))
        return

    url_path = urlparse(request_content.get('url')).path.lstrip("/")
    sessions[url_path].append(websocket)

    logging.debug("added a new websocket, websocket sessions are now %s: ", str(sessions))

    while True:
        try:
            request_content = json.loads(await websocket.recv())
            logging.info("Recieved message from client: %s", str(request_content))
        except websockets.exceptions.WebSocketException as e:
            logging.info("Closing websocket on '%s': %s", url_path, str(e))  # TODO: specifics
            break
        except asyncio.CancelledError:
            logging.debug("Recieved cancel in ws_handler.  Doing nothing though.")
            continue

    sessions[url_path].remove(websocket)
    logging.debug("removed a dead websocket, websocket sessions are now %s: ", str(sessions))


async def process_queue():
    """Processes task_queue, notifying available clients of changed files, which were added by watchdog handler (MyHandler)"""
    try:
        while True:
            while not task_queue.empty():
                p = task_queue.get_nowait()

                if(JINJA_WATCH_PATH in p.parents):
                    p = p.relative_to(JINJA_WATCH_PATH)

                # print(f"doing job with {p} and it matches with websocket: {str(p) in sessions}")
                message = f'{{"command": "reload", "path": "{p}", "liveCSS": false}}'
                if str(p) in sessions:
                    await asyncio.wait([socket.send(message) for socket in sessions[str(p)]])

                if p.name == "index.html" and "" in sessions:
                    await asyncio.wait([socket.send(message) for socket in sessions[""]])

                task_queue.task_done()
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logging.debug("Recieved cancel in process_queue.  Doing nothing though.")


async def ws_server():
    """Creates a websocket server and waits for it to be closed"""
    try:
        logging.info("Serving websockets on http://localhost:%d", WEBSOCKET_SERVER_PORT)
        my_server = await websockets.serve(ws_handler, "localhost", WEBSOCKET_SERVER_PORT)
        await my_server.wait_closed()
    except asyncio.CancelledError:
        logging.debug("Recieved cancel in ws_server.  Doing nothing though.")


async def wss_manager():
    """Entry point for asyncio operations in jinja2html"""
    try:
        logging.info("Setting up websocket server and process queue...")
        tasks = asyncio.gather(ws_server(), process_queue())
        await tasks
    except asyncio.CancelledError:
        logging.debug("Recieved cancel in wss_manager.  Doing nothing though.")


class MyHandler(PatternMatchingEventHandler):
    """Class which handles watchdog events, and either runs jinja renderer or copies new js/css to output folder."""

    def on_modified(self, event):
        """Handles events where a file was modified

        Arguments:
            event {FileSystemEvent} -- The event
        """
        self.__base_update_handler(event)

    def on_created(self, event):
        """Handles events where a file was created

        Arguments:
            event {FileSystemEvent} -- The event
        """
        self.__base_update_handler(event)

    def __base_update_handler(self, event):
        """Base handler for modified/created events

        Arguments:
            event {FileSystemEvent} -- The event
        """
        if event.is_directory:
            return

        path = Path(event.src_path)
        logging.info("%s -> got an update from %s", event.event_type, path)

        if STATIC_SERVER_ROOT in path.parents:
            return

        if JINJA_TEMPLATE_DIR in path.parents or path.name == "config.json":
            for f in JINJA_WATCH_PATH.glob("*.html"):
                build_html(f)
                task_queue.put_nowait(f)

        elif path.suffix.lower() in (".css", ".js"):
            copy_css_js(path)
            for f in JINJA_WATCH_PATH.glob("*.html"):
                task_queue.put_nowait(f)
        else:  # just a normal jinja file
            build_html(path)
            task_queue.put_nowait(path)


def copy_css_js(path):
    """Copies a file from the specified path to the output directory.  Overwrites filename in output directory if it already exists.  Use this for css/js changes.

    Arguments:
        path {pathlib.Path} -- The file to copy to the output directory.
    """
    shutil.copy(path, STATIC_SERVER_ROOT)


def build_html(path, dev_mode=True):
    """Builds the specified jinja template as HTML.

    Arguments:
        path {path.Pathlib} -- The jinja template to build as html.  PRECONDITION: path *is* a valid jinja template

    Keyword Arguments:
        dev_mode {bool} -- Toggles developer mode (whether livereload script should be injected).  Set False if this is for production. (default: {True})
    """
    config = JINJA_WATCH_PATH / "config.json"
    context = json.loads(config.read_text()) if config.is_file() else {}

    output = t_env.get_template(str(path)).render(context)
    if dev_mode:
        try:
            soup = BeautifulSoup(output, "lxml")
            body_tag = soup.find("body")

            # add config for liveReload
            script_tag = soup.new_tag("script")
            script_tag.string = 'window.LiveReloadOptions = {host: "localhost"}'
            body_tag.append(script_tag)

            # actually add the script
            body_tag.append(soup.new_tag("script", src="https://cdn.jsdelivr.net/npm/livereload-js@3.2.1/dist/livereload.min.js",
                                         integrity="sha256-Tm7IcDz9uE2N6RbJ0yeZiLbQRSrtMMMhWEFyG5QD8DI=", crossorigin="anonymous"))
            output = str(soup)
        except AttributeError:
            output = f"ERROR: Malformed or non-existent html in '{path}'.  Doing nothing."
            logging.error(output)

    (STATIC_SERVER_ROOT / path).write_text(output)


def main():
    """Main entry point; handles argument parsing, setup, and teardown"""
    cli_parser = argparse.ArgumentParser(description="Developer friendly rendering of jinja2 templates.")
    cli_parser.add_argument("--generate", action='store_true', help="render all jinja2 files in the current directory, no livereload")
    args = cli_parser.parse_args()

    # setup dev folders
    STATIC_SERVER_ROOT.mkdir(parents=True, exist_ok=True)
    JINJA_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    for f in STATIC_SERVER_ROOT.iterdir():
        f.unlink()
        # print(f"Deleted: {str(f)}")

    for f in Path(JINJA_WATCH_PATH).iterdir():
        if f.is_file():
            ext = f.suffix.lower()
            if ext in (".html", ".htm"):
                build_html(f, not args.generate)
            elif ext in (".js", ".css"):
                copy_css_js(f)

    if not args.generate:
        sh = logging.StreamHandler()
        sh.setFormatter(ColorFormatter())
        logging.basicConfig(level=logging.INFO, handlers=[sh])

        logging.info("Now serving website on http://localhost:%d", STATIC_SERVER_PORT)
        socketserver.TCPServer.allow_reuse_address = True  # don't care about OSErrors
        httpd = socketserver.TCPServer(("", STATIC_SERVER_PORT), partial(http.server.SimpleHTTPRequestHandler, directory=str(STATIC_SERVER_ROOT)))
        Thread(target=httpd.serve_forever, daemon=True).start()

        logging.info("Now watching '%s' for html/js/css changes", JINJA_WATCH_PATH)
        observer = Observer()
        observer.schedule(MyHandler(["*.html", "*.js", "*.css"]), str(JINJA_WATCH_PATH), True)
        observer.daemon = True
        observer.start()

        webbrowser.open_new_tab("http://localhost:" + str(STATIC_SERVER_PORT))

        try:
            asyncio.run(wss_manager())
        except KeyboardInterrupt:
            observer.stop()
            httpd.shutdown()
            logging.warning("Keyboard interrupt - bye.")


class ColorFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("%(asctime)s\n%(levelname)s: %(message)s", "%b %d, %Y %I:%M:%S %p")

        self.__colors = dict(zip(['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'], [f"\x1b[3{x}m" for x in range(8)]))
        self.__formats = {
            "DEBUG": self.__colors.get("cyan"),
            "INFO": self.__colors.get("green"),
            "WARNING": self.__colors.get("yellow"),
            "ERROR": self.__colors.get("red"),
            "CRITICAL": self.__colors.get("red"),
        }

        self.reset = "\x1b[0m"

    def format(self, record):
        record.msg = self.__formats.get(record.levelname) + record.msg + self.reset
        return super().format(record)


if __name__ == '__main__':
    main()
