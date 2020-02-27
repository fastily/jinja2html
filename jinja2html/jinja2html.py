#!/usr/bin/env python

import argparse
import asyncio
import glob
import json
import shutil

import http.server
import socketserver

from collections import defaultdict

from queue import Queue
from pathlib import Path

from functools import partial
from urllib.parse import urlparse
from threading import Thread

from bs4 import BeautifulSoup
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import jinja2
import websockets

sessions = defaultdict(list)

task_queue = Queue()

STATIC_SERVER_PORT = 8000

WEBSOCKET_SERVER_PORT = 35729

STATIC_SERVER_ROOT = "out"

JINJA_WATCH_PATH = "."

JINJA_TEMPLATE_DIR = "templates"

t_env = jinja2.Environment(loader=jinja2.FileSystemLoader(JINJA_WATCH_PATH), autoescape=True)


async def ws_handler(websocket, path):
    request_content = json.loads(await websocket.recv())

    # initial handshake
    print("Recieved from client: " + str(request_content))

    if(request_content.get("command") == "hello"):
        await websocket.send('{"command": "hello", "protocols": ["http://livereload.com/protocols/official-7"], "serverName": "jinja2html"}')
    else:
        print("ERROR: Something went wrong during handshake: " + str(request_content))
        return

    request_content = json.loads(await websocket.recv())

    #  {'command': 'info', 'plugins': {'less': {'disable': False, 'version': '1.0'}}, 'url': 'http://localhost:8000/ok.html'}
    if(request_content.get("command") == "info"):
        print("Now connected to " + request_content.get('url'))
    else:
        print("ERROR: Something went wrong during response from handshake: " + str(request_content))
        return

    url_path = urlparse(request_content.get('url')).path
    sessions[url_path].append(websocket)
    print(sessions)

    try:
        while True:
            request_content = json.loads(await websocket.recv())
            print("Recieved message from client: " + str(request_content))
    except websockets.exceptions.ConnectionClosedError:
        print("socket was closed by client.  Closing socket on our end")
    except asyncio.CancelledError:
        pass  # nobody cares
    finally:
        sessions[url_path].remove(websocket)
        print(sessions)


async def process_queue():
    while True:
        while not task_queue.empty():
            element = task_queue.get_nowait()

            if element.startswith(JINJA_WATCH_PATH):
                element = element[len(JINJA_WATCH_PATH):]

            print(f"doing job with {element} and it matches with websocket: {element in sessions}")
            message = f'{{"command": "reload", "path": "{element}", "liveCSS": false}}'
            if element in sessions:
                await asyncio.wait([socket.send(message) for socket in sessions[element]])

            if element == "/index.html" and "/" in sessions:
                await asyncio.wait([socket.send(message) for socket in sessions["/"]])

            task_queue.task_done()
        await asyncio.sleep(1)


async def ws_server():
    try:
        print("Serving websockets on localhost:" + str(WEBSOCKET_SERVER_PORT))
        my_server = await websockets.serve(ws_handler, "localhost", WEBSOCKET_SERVER_PORT)
        await my_server.wait_closed()
    except asyncio.CancelledError:
        my_server.close()


async def wss_manager():
    try:
        tasks = asyncio.gather(ws_server(), process_queue())
        await tasks
    except asyncio.CancelledError:
        tasks.cancel()
        print("shutting down webserver")


class MyHandler(PatternMatchingEventHandler):
    def on_modified(self, event):
        self.__base_update_handler(event)

    def on_created(self, event):
        self.__base_update_handler(event)

    def __base_update_handler(self, event):
        print(self.patterns)
        if event.is_directory:
            return

        path = event.src_path
        print(f"{event.event_type} -> got an update from {path}")

        if path.startswith(JINJA_WATCH_PATH + "/" + STATIC_SERVER_ROOT):
            return

        if path.startswith(JINJA_WATCH_PATH + "/" + JINJA_TEMPLATE_DIR) or path.endswith("/config.json"):
            for path in glob.glob(JINJA_WATCH_PATH + "/*.html"):
                build_html(path)
                task_queue.put_nowait(path)
        elif path.endswith((".css", ".CSS", ".js", ".JS")):
            copy_css_js(path)
            for path in glob.glob(JINJA_WATCH_PATH + "/*.html"):
                copy_css_js(path)
                task_queue.put_nowait(path)
        else:  # just a normal jinja file
            build_html(path)
            task_queue.put_nowait(path)


def copy_css_js(path):
    shutil.copy(path, STATIC_SERVER_ROOT)


def build_html(path, dev_mode=True):
    if Path(JINJA_WATCH_PATH + "/config.json").is_file():
        with open(JINJA_WATCH_PATH + "/config.json") as json_file:
            context = json.load(json_file)
    else:
        context = {}

    output = t_env.get_template(path).render(context)
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
            output = soup.prettify()
        except AttributeError:
            output = f"ERROR: Malformed or non-existent html in '{path}'.  Doing nothing."
            print(output)

    with open(f"{STATIC_SERVER_ROOT}/{path}", "w") as f:
        f.write(output)

def main():
    cli_parser = argparse.ArgumentParser(description="Developer friendly rendering of jinja2 templates.")
    cli_parser.add_argument("--generate", action='store_true', help="render all jinja2 files in the current directory, no livereload")
    args = cli_parser.parse_args()

    # setup dev folders
    Path(STATIC_SERVER_ROOT).mkdir(parents=True, exist_ok=True)
    Path(JINJA_TEMPLATE_DIR).mkdir(parents=True, exist_ok=True)

    for p in Path(JINJA_WATCH_PATH).glob(STATIC_SERVER_ROOT + "/*"):
        p.unlink()
        print(f"Deleted: {str(p)}")

    for p in Path(JINJA_WATCH_PATH).glob("*"):
        if p.is_file():
            ext = p.suffix.lower()
            if ext in (".html", ".htm"):
                build_html(str(p), not args.generate)
            elif ext in (".js", ".css"):
                copy_css_js(str(p))

    if not args.generate:
        print("serving static files on localhost:" + str(STATIC_SERVER_PORT))
        httpd = socketserver.TCPServer(("", STATIC_SERVER_PORT), partial(http.server.SimpleHTTPRequestHandler, directory=STATIC_SERVER_ROOT))
        Thread(target=httpd.serve_forever, daemon=True).start()

        observer = Observer()
        observer.schedule(MyHandler(["*.html", "*.js", "*.css"]), JINJA_WATCH_PATH, recursive=True)
        observer.daemon = True
        observer.start()

        try:
            main_coroutine = wss_manager()
            asyncio.run(main_coroutine)
        except KeyboardInterrupt:
            main_coroutine.close()
            observer.stop()
            httpd.shutdown()
            print("\nKeyboard interrupt!  Bye.")


if __name__ == '__main__':
    main()