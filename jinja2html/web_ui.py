"""Classes & methods supporting livereload functionality"""

import asyncio
import json
import logging

from collections import defaultdict, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from webbrowser import open_new_tab

from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.routing import Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket
from uvicorn import Config, Server
from watchfiles import awatch, Change

from .build_context import Context
from .website_manager import WebsiteManager
from .utils import is_css_js

log = logging.getLogger(__name__)


_SESSIONS = defaultdict(set)


class CustomServer(Server):
    """A uvicorn `Server` that doesn't configure signal handlers (so ctrl+c works).  This is a hack, pending resolution of [https://github.com/encode/uvicorn/issues/1579]"""

    def install_signal_handlers(self):
        """Installs signal handlers.  This implementation deliberately does nothing."""
        pass


class LiveReloadEndpoint(WebSocketEndpoint):
    """Handles websocket livereload functionality for use with Starlette"""

    encoding = "text"  # this is needed for the superclass to work correctly
    _ALL_SOCKETS = {}

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        """Handles incoming websocket messages.

        Args:
            websocket (WebSocket): The websocket connection which the message was sent over.
            data (Any): The message from the client
        """
        request_content = json.loads(data)
        log.debug("received message via websocket from a client: %s", request_content)

        # initial handshake
        if websocket not in LiveReloadEndpoint._ALL_SOCKETS:
            if request_content.get("command") == "hello":
                log.info("Acknowledging a hello handshake request from a livereload client...")

                LiveReloadEndpoint._ALL_SOCKETS[websocket] = None
                await websocket.send_json({"command": "hello", "protocols": ["http://livereload.com/protocols/official-7"], "serverName": "jinja2html"})
            else:
                log.error("Bad liveserver handshake request from a client: %s", request_content)

        #  sample reply: {'command': 'info', 'plugins': {'less': {'disable': False, 'version': '1.0'}}, 'url': 'http://localhost:8000/ok.html'}
        elif request_content.get("command") == "info" and (url := request_content.get('url')):
            url_path = urlparse(url).path.lstrip("/")
            _SESSIONS[url_path].add(websocket)
            LiveReloadEndpoint._ALL_SOCKETS[websocket] = url_path

            log.info("New livereload session estasblished at '%s'", request_content.get('url'))
            log.debug("Websocket sessions are now: %s", _SESSIONS)
        else:
            log.info("Got message from client, it said: %s", data)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        """Handles websockets disconnecting

        Args:
            websocket (WebSocket): The websocket connection which disconnected
            close_code (int): The closing status code
        """

        log.debug("Recieved disconnect message with code %d", close_code)

        if (urlpath := LiveReloadEndpoint._ALL_SOCKETS.pop(websocket, None)) is not None:
            _SESSIONS[urlpath].remove(websocket)
            log.debug("removed a closed websocket, websocket sessions are now %s: ", _SESSIONS)


async def html_server(context: Context, port: int) -> None:
    """The html server UI coroutine.  Also opens a web browser to localhost:port.

    Args:
        context (Context): The website context to use
        port (int, optional): The port to bind the webserver to.
    """
    open_new_tab(f"http://localhost:{port}")
    await CustomServer(Config(Starlette(debug=True, routes=[Mount("/", app=StaticFiles(directory=context.output_dir, html=True))]), port=port)).serve()


async def websocket_server() -> None:
    """The websocket UI coroutine"""
    await CustomServer(Config(Starlette(debug=True, routes=[WebSocketRoute("/livereload", LiveReloadEndpoint)]), port=35729)).serve()


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
            message = {"command": "reload", "path": stub, "liveCSS": False}

            if sockets := _SESSIONS.get(stub):
                await send_msgs(message, sockets)

            if p.name == "index.html" and (sockets := _SESSIONS.get("")):
                await send_msgs(message, sockets)


async def send_msgs(message: dict, sockets: Iterable[WebSocket]) -> None:
    """Convenience method, sends `message` to each `WebSocket` in `sockets`.

    Args:
        message (dict): The message to send - this will be converted to json
        sockets (Iterable[WebSocket]): The `WebSocket` objects to send `message` to.
    """
    await asyncio.wait({asyncio.create_task(socket.send_json(message)) for socket in sockets})


async def main_loop(wm: WebsiteManager, html_port: int) -> None:
    """Entry point for asyncio operations in jinja2html

    Args:
        wm (WebsiteManager): The WebsiteManager to associate with this asyncio loop
        html_port (int): The port the html server should be bound to
    """
    try:
        log.info("Setting up websocket server and process queue...")
        await asyncio.gather(changed_files_handler(wm), html_server(wm.context, html_port), websocket_server(), return_exceptions=True)
    except asyncio.CancelledError:
        log.debug("Received cancel request!")
