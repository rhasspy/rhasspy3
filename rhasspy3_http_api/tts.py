import argparse
import io
import logging

from quart import Response, request, Quart

from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.tts import synthesize
from rhasspy3.snd import play

_LOGGER = logging.getLogger(__name__)


def add_tts(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/api/text-to-speech", methods=["GET", "POST"])
    async def api_text_to_speech() -> Response:
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        tts_program = request.args.get("tts_program", pipeline.tts)
        assert tts_program, "No tts program"
        _LOGGER.debug("text-to-speech: tts=%s, text='%s'", tts_program, text)

        with io.BytesIO() as wav_out:
            await synthesize(rhasspy, tts_program, text, wav_out)
            wav_bytes = wav_out.getvalue()
            _LOGGER.debug("text-to-speech: wav=%s byte(s)", len(wav_bytes))

            return Response(wav_bytes, mimetype="audio/wav")

    @app.route("/api/speak-text", methods=["GET", "POST"])
    async def api_speak_text() -> str:
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        tts_program = request.args.get("tts_program", pipeline.tts)
        snd_program = request.args.get("snd_program", pipeline.snd)
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        assert tts_program, "No tts program"
        assert snd_program, "No snd program"
        _LOGGER.debug(
            "speak-text: tts=%s, snd=%s, text='%s'", tts_program, snd_program, text
        )

        with io.BytesIO() as wav_out:
            await synthesize(rhasspy, tts_program, text, wav_out)
            wav_bytes = wav_out.getvalue()
            _LOGGER.debug("text-to-speech: wav=%s byte(s)", len(wav_bytes))

            wav_out.seek(0)
            await play(rhasspy, snd_program, wav_out, samples_per_chunk, sleep=True)

        return "OK"
