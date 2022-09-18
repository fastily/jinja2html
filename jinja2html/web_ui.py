import asyncio
import json
import logging

from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.routing import Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from uvicorn import Config, Server
from watchfiles import awatch, Change

from .build_context import Context
from .website_manager import WebsiteManager
from .utils import is_css_js

log = logging.getLogger(__name__)


_SESSIONS = defaultdict(set)
_WEBSOCKET_SERVER_PORT = 35729


class CustomServer(Server):
    """A uvicorn `Server` that doesn't configure signal handlers (so ctrl+c works).  This is a hack."""

    def install_signal_handlers(self):
        """Installs signal handlers.  This implementation deliberately does nothing."""
        pass


class LiveReloadServer(WebSocketEndpoint):

    encoding = "text"  # this is needed for the superclass to work correctly

    _ALL_SOCKETS = {}

    async def on_receive(self, websocket, data):

        request_content = json.loads(data)
        log.debug("received message via websocket from a client: %s", request_content)

        # initial handshake
        if websocket not in LiveReloadServer._ALL_SOCKETS:
            if request_content.get("command") == "hello":
                log.info("Acknowleding a hello handshake request from a livereload client...")

                LiveReloadServer._ALL_SOCKETS[websocket] = None
                await websocket.send_json({"command": "hello", "protocols": ["http://livereload.com/protocols/official-7"], "serverName": "jinja2html"})
            else:
                log.error("Bad liveserver handshake request from a client: %s", request_content)

        #  sample reply: {'command': 'info', 'plugins': {'less': {'disable': False, 'version': '1.0'}}, 'url': 'http://localhost:8000/ok.html'}
        elif request_content.get("command") == "info" and (url := request_content.get('url')):
            url_path = urlparse(url).path.lstrip("/")
            _SESSIONS[url_path].add(websocket)
            LiveReloadServer._ALL_SOCKETS[websocket] = url_path

            log.info("New livereload session estasblished at '%s'", request_content.get('url'))
            log.debug("Websocket sessions are now: %s", _SESSIONS)
        else:
            log.info("Got message from client, it said: %s", data)

    async def on_disconnect(self, websocket, close_code):

        log.debug("Recieved disconnect request: %d", close_code)

        if urlpath := LiveReloadServer._ALL_SOCKETS.pop(websocket, None):
            _SESSIONS[urlpath].remove(websocket)
            log.debug("removed a closed websocket, websocket sessions are now %s: ", _SESSIONS)


async def html_server(context: Context, port: int = 8000) -> None:
    """The html server UI coroutine

    Args:
        context (Context): The website context to use
        port (int, optional): The port to bind the webserver to. Defaults to 8000.
    """
    await CustomServer(Config(Starlette(debug=True, routes=[Mount("/", app=StaticFiles(directory=context.output_dir, html=True))]), port=port)).serve()


async def websocket_server() -> None:
    """The websocket ui coroutine"""
    await CustomServer(Config(Starlette(debug=True, routes=[WebSocketRoute("/livereload", LiveReloadServer)]), port=_WEBSOCKET_SERVER_PORT)).serve()


# async def ws_handler(websocket: websockets.WebSocketServerProtocol) -> None:
#     """Handler managing an individual websocket's lifecycle, for use with `websockets.serve`

#     Args:
#         websocket (websockets.WebSocketServerProtocol): The websocket object representing a new websocket connection.
#     """
#     request_content = json.loads(await websocket.recv())
#     log.debug("received message via websocket from a client: %s", request_content)

#     if request_content.get("command") == "hello":  # initial handshake
#         await websocket.send('{"command": "hello", "protocols": ["http://livereload.com/protocols/official-7"], "serverName": "jinja2html"}')
#     else:
#         log.error("Bad liveserver handshake request from a client: %s", request_content)
#         return

#     request_content = json.loads(await websocket.recv())

#     #  sample reply: {'command': 'info', 'plugins': {'less': {'disable': False, 'version': '1.0'}}, 'url': 'http://localhost:8000/ok.html'}
#     if request_content.get("command") == "info":
#         log.info("New websocket connection estasblished at: %s", request_content.get('url'))
#     else:
#         log.error("Something went wrong during response from handshake: %s", request_content)
#         return

#     url_path = urlparse(request_content.get('url')).path.lstrip("/")
#     _SESSIONS[url_path].append(websocket)

#     log.debug("added a new websocket, websocket sessions are now %s: ", _SESSIONS)

#     try:
#         async for message in websocket:
#             log.info("received message from client: %s", message)
#     except websockets.exceptions.WebSocketException as e:
#         log.info("Closing websocket on '%s'", url_path)  # TODO: specifics
#     except asyncio.CancelledError:
#         log.debug("received cancel in ws_handler.  Doing nothing though.")

#     _SESSIONS[url_path].remove(websocket)
#     log.debug("removed a dead websocket, websocket sessions are now %s: ", _SESSIONS)


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
                for socket in sockets:
                    await socket.send_json(message)

                # await asyncio.wait([asyncio.create_task(socket.send(message)) for socket in _SESSIONS[stub]])

            if p.name == "index.html" and (sockets := _SESSIONS.get("")):
                for socket in sockets:
                    await socket.send_json(message)

                # await asyncio.wait([asyncio.create_task(socket.send(message)) for socket in _SESSIONS[""]])


# async def ws_server() -> None:
#     """Creates a websocket server and waits for it to be closed"""
#     try:
#         log.info("Serving websockets on http://localhost:%d", _WEBSOCKET_SERVER_PORT)
#         async with websockets.serve(ws_handler, "localhost", _WEBSOCKET_SERVER_PORT):
#             await asyncio.Future()

#     except asyncio.CancelledError:
#         log.debug("Received cancel in ws_server.  Doing nothing though.")


async def main_loop(wm: WebsiteManager) -> None:
    """Entry point for asyncio operations in jinja2html

    Args:
        wm (WebsiteManager): The WebsiteManager to associate with this asyncio loop
    """
    try:
        log.info("Setting up websocket server and process queue...")
        await asyncio.gather(changed_files_handler(wm), html_server(wm.context), websocket_server())
    except asyncio.CancelledError:
        log.debug("Received cancel in wss_manager.  Doing nothing though.")
