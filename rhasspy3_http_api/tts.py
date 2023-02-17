import argparse
import io
import logging

from quart import Response, request, Quart, jsonify

from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.tts import synthesize
from rhasspy3.snd import play

_LOGGER = logging.getLogger(__name__)


def add_tts(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/tts/synthesize", methods=["GET", "POST"])
    async def http_tts_synthesize() -> Response:
        """Synthesize a WAV file from text."""
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        tts_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        tts_program = request.args.get("tts_program") or tts_pipeline.tts
        assert tts_program, "No tts program"
        _LOGGER.debug("synthesize: tts=%s, text='%s'", tts_program, text)

        with io.BytesIO() as wav_out:
            await synthesize(rhasspy, tts_program, text, wav_out)
            wav_bytes = wav_out.getvalue()
            _LOGGER.debug("synthesize: wav=%s byte(s)", len(wav_bytes))

            return Response(wav_bytes, mimetype="audio/wav")

    @app.route("/tts/speak", methods=["GET", "POST"])
    async def http_tts_speak() -> Response:
        """Synthesize audio from text and play."""
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        tts_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        tts_program = request.args.get("tts_program") or tts_pipeline.tts
        snd_program = request.args.get("snd_program") or tts_pipeline.snd
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        assert tts_program, "No tts program"
        assert snd_program, "No snd program"
        _LOGGER.debug(
            "synthesize: tts=%s, snd=%s, text='%s'", tts_program, snd_program, text
        )

        with io.BytesIO() as wav_out:
            await synthesize(rhasspy, tts_program, text, wav_out)
            wav_bytes = wav_out.getvalue()
            _LOGGER.debug("synthesize: wav=%s byte(s)", len(wav_bytes))

            wav_out.seek(0)
            played = await play(rhasspy, snd_program, wav_out, samples_per_chunk)

        return jsonify(played.event().to_dict() if played is not None else {})
