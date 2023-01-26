import asyncio
import argparse
import logging
import io
import wave
from pathlib import Path
from typing import Optional, Tuple
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
from swagger_ui import api_doc

from rhasspy3.asr import transcribe
from rhasspy3.core import Rhasspy
from rhasspy3.audio import wav_to_chunks, AudioStart, AudioStop, AudioChunk
from rhasspy3.snd import play
from rhasspy3.tts import synthesize
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.program import create_process

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("rhasspy")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Configuration directory",
    )
    parser.add_argument(
        "--pipeline", required=True, help="Name of default pipeline to run"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host of HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=12101, help="Port of HTTP server (default: 12101)"
    )
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    pipeline = rhasspy.config.pipelines[args.pipeline]

    template_dir = _DIR / "templates"
    img_dir = _DIR / "img"

    app = Quart("rhasspy3", template_folder=str(template_dir))
    app.secret_key = str(uuid4())
    app = quart_cors.cors(app)

    @app.errorhandler(Exception)
    async def handle_error(err) -> Tuple[str, int]:
        """Return error as text."""
        _LOGGER.exception(err)
        return (f"{err.__class__.__name__}: {err}", 500)

    @app.route("/", methods=["GET"])
    async def page_index() -> str:
        """Render main web page."""
        return await render_template("index.html")

    @app.route("/img/<path:filename>", methods=["GET"])
    async def img(filename) -> Response:
        """Image static endpoint."""
        return await send_from_directory(img_dir, filename)

    @app.route("/api/play-wav", methods=["POST"])
    async def api_play_wav() -> str:
        wav_bytes = await request.data
        program = request.args.get("program", pipeline.snd)
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        with io.BytesIO(wav_bytes) as wav_in:
            await play(rhasspy, program, wav_in, samples_per_chunk)

        return str(len(wav_bytes))

    @app.route("/api/speech-to-text", methods=["POST"])
    async def api_speech_to_text() -> str:
        wav_bytes = await request.data
        program = request.args.get("program", pipeline.asr)
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        with io.BytesIO(wav_bytes) as wav_in:
            transcript = await transcribe(rhasspy, program, wav_in, samples_per_chunk)

        return transcript.text if transcript is not None else ""

    @app.route("/api/text-to-speech", methods=["GET", "POST"])
    async def api_text_to_speech() -> Response:
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        program = request.args.get("program", pipeline.tts)

        with io.BytesIO() as wav_out:
            await synthesize(rhasspy, program, text, wav_out)
            return Response(wav_out.getvalue(), mimetype="audio/wav")

    @app.route("/api/version", methods=["POST"])
    async def api_version() -> str:
        return "3.0.0"

    api_doc(
        app,
        config_path=_DIR / "swagger.yaml",
        url_prefix="/openapi",
        title="Rhasspy",
    )

    hyp_config = hypercorn.config.Config()
    hyp_config.bind = [f"{args.host}:{args.port}"]

    try:
        asyncio.run(hypercorn.asyncio.serve(app, hyp_config))
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
