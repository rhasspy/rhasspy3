import argparse
import io
import logging

from quart import Response, request, Quart, jsonify

from rhasspy3.asr import transcribe
from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.intent import recognize, Intent

_LOGGER = logging.getLogger(__name__)


def add_asr(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/api/speech-to-text", methods=["POST"])
    async def api_speech_to_text() -> str:
        wav_bytes = await request.data
        program = request.args.get("program", pipeline.asr)
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        _LOGGER.debug(
            "speech-to-text: asr=%s, wav=%s byte(s)", program, len(wav_bytes)
        )

        with io.BytesIO(wav_bytes) as wav_in:
            transcript = await transcribe(rhasspy, program, wav_in, samples_per_chunk)

        text = transcript.text if transcript is not None else ""
        _LOGGER.debug("speech-to-text: text='%s'", text)

        return text

    @app.route("/api/speech-to-intent", methods=["GET", "POST"])
    async def api_speech_to_intent() -> Response:
        wav_bytes = await request.data
        asr_program = request.args.get("asr_program", pipeline.asr)
        intent_program = request.args.get("intent_program", pipeline.intent)
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        _LOGGER.debug(
            "speech-to-intent: asr=%s, intent=%s, wav=%s byte(s)",
            asr_program,
            intent_program,
            len(wav_bytes),
        )

        with io.BytesIO(wav_bytes) as wav_in:
            transcript = await transcribe(
                rhasspy, asr_program, wav_in, samples_per_chunk
            )

        text = transcript.text if transcript is not None else ""
        _LOGGER.debug("speech-to-intent: text='%s'", text)

        data = {}
        result = await recognize(rhasspy, intent_program, text)
        _LOGGER.debug("speech-to-intent: result=%s", result)

        if isinstance(result, Intent):
            data = result.to_rhasspy()

        return jsonify(data)
