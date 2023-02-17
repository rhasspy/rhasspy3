import asyncio
import argparse
import logging
import os
import io
import threading
import subprocess
import wave
from collections import deque
from pathlib import Path
from typing import Deque, Optional, Tuple
from uuid import uuid4

import hypercorn
import quart_cors
from quart import (
    Quart,
    Response,
    jsonify,
    request,
    render_template,
    send_from_directory,
)

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK
from rhasspy3.core import Rhasspy

from .asr import add_asr
from .intent import add_intent
from .snd import add_snd
from .tts import add_tts
from .wake import add_wake
from .pipeline import add_pipeline
from .handle import add_handle

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("rhasspy")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument(
        "--pipeline", default="default", help="Name of default pipeline to run"
    )
    parser.add_argument(
        "--server",
        nargs=2,
        action="append",
        metavar=("domain", "name"),
        help="Domain/name of server(s) to run",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host of HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=13331, help="Port of HTTP server (default: 13331)"
    )
    parser.add_argument(
        "--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK
    )
    parser.add_argument("--asr-chunks-to-buffer", type=int, default=0)
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    pipeline = rhasspy.config.pipelines[args.pipeline]

    template_dir = _DIR / "templates"
    img_dir = _DIR / "img"
    css_dir = _DIR / "css"

    app = Quart("rhasspy3", template_folder=str(template_dir))
    app.secret_key = str(uuid4())

    # Monkey patch quart_cors to get rid of non-standard requirement that
    # websockets have origin header set.
    def _apply_websocket_cors(*args, **kwargs):
        """Allow null origin."""
        pass

    # pylint: disable=protected-access
    quart_cors._apply_websocket_cors = _apply_websocket_cors
    app = quart_cors.cors(app, allow_origin="*")

    add_wake(app, rhasspy, pipeline, args)
    add_asr(app, rhasspy, pipeline, args)
    add_intent(app, rhasspy, pipeline, args)
    add_handle(app, rhasspy, pipeline, args)
    add_snd(app, rhasspy, pipeline, args)
    add_tts(app, rhasspy, pipeline, args)
    add_pipeline(app, rhasspy, pipeline, args)

    @app.errorhandler(Exception)
    async def handle_error(err) -> Tuple[str, int]:
        """Return error as text."""
        _LOGGER.exception(err)
        return (f"{err.__class__.__name__}: {err}", 500)

    @app.route("/", methods=["GET"])
    async def page_index() -> str:
        """Render main web page."""
        return await render_template("index.html", config=rhasspy.config)

    @app.route("/img/<path:filename>", methods=["GET"])
    async def img(filename) -> Response:
        """Image static endpoint."""
        return await send_from_directory(img_dir, filename)

    @app.route("/css/<path:filename>", methods=["GET"])
    async def css(filename) -> Response:
        """css static endpoint."""
        return await send_from_directory(css_dir, filename)

    @app.route("/config", methods=["GET"])
    async def http_config() -> Response:
        return jsonify(rhasspy.config)

    @app.route("/version", methods=["POST"])
    async def http_version() -> str:
        return "3.0.0"

    hyp_config = hypercorn.config.Config()
    hyp_config.bind = [f"{args.host}:{args.port}"]

    if args.server:
        run_servers(rhasspy, args.server)

    try:
        asyncio.run(hypercorn.asyncio.serve(app, hyp_config))
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


def run_servers(rhasspy, servers):
    def run_server(domain: str, name: str):
        try:
            command = [
                "server_run.py",
                "--config",
                str(rhasspy.config_dir),
                domain,
                name,
            ]
            env = dict(os.environ)
            env["PATH"] = f'{rhasspy.base_dir}/bin:{env["PATH"]}'
            _LOGGER.debug(command)
            _LOGGER.info("Starting %s %s", domain, name)
            subprocess.run(command, check=True, cwd=rhasspy.base_dir, env=env)
        except Exception:
            _LOGGER.exception(
                "Unexpected error running server: domain=%s, name=%s", domain, name
            )

    for domain, server_name in servers:
        threading.Thread(
            target=run_server, args=(domain, server_name), daemon=True
        ).start()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
