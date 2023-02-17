import argparse
import io
import logging
import json

from quart import request, Quart, websocket, Response, jsonify

from rhasspy3.audio import (
    AudioStop,
    DEFAULT_OUT_CHANNELS,
    DEFAULT_OUT_RATE,
    DEFAULT_OUT_WIDTH,
)
from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.event import Event
from rhasspy3.snd import play, play_stream

_LOGGER = logging.getLogger(__name__)


def add_snd(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/snd/play", methods=["POST"])
    async def http_snd_play() -> Response:
        """Play WAV file."""
        wav_bytes = await request.data
        snd_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        snd_program = request.args.get("snd_program") or snd_pipeline.snd
        assert snd_program, "Missing program for snd"

        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        _LOGGER.debug("play: snd=%s, wav=%s byte(s)", snd_program, len(wav_bytes))

        with io.BytesIO(wav_bytes) as wav_in:
            played = await play(
                rhasspy,
                snd_program,
                wav_in,
                samples_per_chunk,
            )

        return jsonify(played.event().to_dict() if played is not None else {})

    @app.websocket("/snd/play")
    async def ws_snd_play():
        """Play websocket audio stream."""
        snd_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        snd_program = websocket.args.get("snd_program") or snd_pipeline.snd
        assert snd_program, "Missing program for snd"

        rate = int(websocket.args.get("rate", DEFAULT_OUT_RATE))
        width = int(websocket.args.get("width", DEFAULT_OUT_WIDTH))
        channels = int(websocket.args.get("channels", DEFAULT_OUT_CHANNELS))

        _LOGGER.debug("play: snd=%s", snd_program)

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

        played = await play_stream(
            rhasspy, snd_program, audio_stream(), rate, width, channels
        )

        await websocket.send_json(
            played.event().to_dict() if played is not None else {}
        )
