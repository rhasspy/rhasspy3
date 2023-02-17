import argparse
import io
import json
import logging

from quart import Quart, Response, jsonify, request, websocket

from rhasspy3.asr import transcribe, transcribe_stream
from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    AudioStop,
)
from rhasspy3.config import PipelineConfig
from rhasspy3.core import Rhasspy
from rhasspy3.event import Event

_LOGGER = logging.getLogger(__name__)


def add_asr(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/asr/transcribe", methods=["POST"])
    async def http_asr_transcribe() -> Response:
        """Transcribe a WAV file."""
        wav_bytes = await request.data
        asr_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )

        asr_program = request.args.get("asr_program") or asr_pipeline.asr
        assert asr_program, "Missing program for asr"

        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        _LOGGER.debug("transcribe: asr=%s, wav=%s byte(s)", asr_program, len(wav_bytes))

        with io.BytesIO(wav_bytes) as wav_in:
            transcript = await transcribe(
                rhasspy, asr_program, wav_in, samples_per_chunk
            )

        _LOGGER.debug("transcribe: transcript='%s'", transcript)
        return jsonify(transcript.event().to_dict() if transcript is not None else {})

    @app.websocket("/asr/transcribe")
    async def ws_asr_transcribe():
        """Transcribe a websocket audio stream."""
        asr_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        asr_program = websocket.args.get("asr_program") or asr_pipeline.asr
        assert asr_program, "Missing program for asr"

        rate = int(websocket.args.get("rate", DEFAULT_IN_RATE))
        width = int(websocket.args.get("width", DEFAULT_IN_WIDTH))
        channels = int(websocket.args.get("channels", DEFAULT_IN_CHANNELS))

        _LOGGER.debug("transcribe: asr=%s", asr_program)

        async def audio_stream():
            while True:
                data = await websocket.receive()
                if not data:
                    # Empty message signals stop
                    break

                if isinstance(data, bytes):
                    # Raw audio
                    yield data
                else:
                    event = Event.from_dict(json.loads(data))
                    if AudioStop.is_type(event.type):
                        # Stop event
                        break

        transcript = await transcribe_stream(
            rhasspy, asr_program, audio_stream(), rate, width, channels
        )

        _LOGGER.debug("transcribe: transcript='%s'", transcript)

        await websocket.send_json(
            transcript.event().to_dict() if transcript is not None else {}
        )
