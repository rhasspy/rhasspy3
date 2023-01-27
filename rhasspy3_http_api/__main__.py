import asyncio
import argparse
import logging
import io
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
from swagger_ui import api_doc

from rhasspy3.asr import transcribe, DOMAIN as ASR_DOMAIN, Transcript
from rhasspy3.core import Rhasspy
from rhasspy3.audio import wav_to_chunks, AudioStart, AudioStop, AudioChunk
from rhasspy3.intent import recognize, Intent
from rhasspy3.snd import play
from rhasspy3.tts import synthesize
from rhasspy3.event import async_read_event, async_write_event, Event
from rhasspy3.program import create_process
from rhasspy3.wake import detect
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.vad import segment

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
    parser.add_argument("--asr-chunks-to-buffer", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

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

    @app.route("/api/speech-to-intent", methods=["GET", "POST"])
    async def api_speech_to_intent() -> Response:
        wav_bytes = await request.data
        asr_program = request.args.get("asr_program", pipeline.asr)
        intent_program = request.args.get("intent_program", pipeline.intent)
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        with io.BytesIO(wav_bytes) as wav_in:
            transcript = await transcribe(
                rhasspy, asr_program, wav_in, samples_per_chunk
            )

        data = {}
        if transcript is not None:
            result = await recognize(rhasspy, intent_program, transcript.text)

            # TODO: Post-process transcript
            if isinstance(result, Intent):
                data = result.to_rhasspy()

        return jsonify(data)

    @app.route("/api/text-to-intent", methods=["GET", "POST"])
    async def api_text_to_intent() -> Response:
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        program = request.args.get("program", pipeline.intent)
        result = await recognize(rhasspy, program, text)

        data = {}
        if isinstance(result, Intent):
            data = result.to_rhasspy()

        return jsonify(data)

    @app.route("/api/wait-for-wake", methods=["GET", "POST"])
    async def api_wait_for_wake() -> str:
        mic_program = request.args.get("mic_program", pipeline.mic)
        wake_program = request.args.get("wake_program", pipeline.wake)

        mic_proc = await create_process(rhasspy, MIC_DOMAIN, mic_program)
        try:
            assert mic_proc.stdout is not None
            result = await detect(rhasspy, wake_program, mic_proc.stdout)
            if result is not None:
                return result.name or ""
        finally:
            mic_proc.terminate()
            await mic_proc.wait()

        return ""

    @app.route("/api/listen-for-command", methods=["GET", "POST"])
    async def api_listen_for_command() -> Response:
        mic_program = request.args.get("mic_program", pipeline.mic)
        wake_program = request.args.get("wake_program", pipeline.wake)
        vad_program = request.args.get("vad_program", pipeline.vad)
        asr_program = request.args.get("asr_program", pipeline.asr)
        intent_program = request.args.get("intent_program", pipeline.intent)
        asr_chunks_to_buffer = int(
            request.args.get("asr_chunks_to_buffer", args.asr_chunks_to_buffer)
        )

        if asr_chunks_to_buffer > 0:
            chunk_buffer: Optional[Deque[Event]] = deque(maxlen=asr_chunks_to_buffer)
        else:
            chunk_buffer = None

        data = {}
        mic_proc = await create_process(rhasspy, MIC_DOMAIN, mic_program)
        try:
            assert mic_proc.stdout is not None
            asr_proc = await create_process(rhasspy, ASR_DOMAIN, asr_program)
            try:
                assert asr_proc.stdin is not None
                assert asr_proc.stdout is not None

                detect_result = await detect(
                    rhasspy, wake_program, mic_proc.stdout, chunk_buffer
                )
                if detect_result is not None:
                    _LOGGER.debug("Wake word detected: %s", detect_result)
                    await segment(
                        rhasspy,
                        vad_program,
                        mic_proc.stdout,
                        asr_proc.stdin,
                        chunk_buffer,
                    )
                    while True:
                        asr_event = await async_read_event(asr_proc.stdout)
                        if asr_event is None:
                            break

                        _LOGGER.debug(asr_event)

                        if Transcript.is_type(asr_event.type):
                            transcript = Transcript.from_event(asr_event)
                            if transcript.text:
                                recognize_result = await recognize(
                                    rhasspy, intent_program, transcript.text
                                )
                                if isinstance(recognize_result, Intent):
                                    data = recognize_result.to_rhasspy()
                            break
            finally:
                asr_proc.terminate()
                await asr_proc.wait()
        finally:
            mic_proc.terminate()
            await mic_proc.wait()

        return jsonify(data)

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
