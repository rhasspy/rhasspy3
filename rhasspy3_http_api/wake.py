import argparse
import io
import json
import logging
import wave

from quart import Quart, Response, jsonify, request, websocket

from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    AudioStop,
)
from rhasspy3.config import PipelineConfig
from rhasspy3.core import Rhasspy
from rhasspy3.event import Event
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.program import create_process
from rhasspy3.wake import detect, detect_stream

_LOGGER = logging.getLogger(__name__)


def add_wake(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/wake/detect", methods=["GET", "POST"])
    async def http_wake_detect() -> Response:
        """Detect wake word in WAV file."""
        wav_bytes = await request.data
        wake_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        wake_program = request.args.get("wake_program") or wake_pipeline.wake
        assert wake_program, "Missing program for wake"

        if wav_bytes:
            # Detect from WAV
            samples_per_chunk = int(
                request.args.get("samples_per_chunk", args.samples_per_chunk)
            )

            _LOGGER.debug(
                "detect: wake=%s, wav=%s byte(s)", wake_program, len(wav_bytes)
            )

            with io.BytesIO(wav_bytes) as wav_io:
                wav_file: wave.Wave_read = wave.open(wav_io, "rb")
                with wav_file:

                    async def audio_stream():
                        chunk = wav_file.readframes(samples_per_chunk)
                        while chunk:
                            yield chunk
                            chunk = wav_file.readframes(samples_per_chunk)

                    detection = await detect_stream(
                        rhasspy,
                        wake_program,
                        audio_stream(),
                        wav_file.getframerate(),
                        wav_file.getsampwidth(),
                        wav_file.getnchannels(),
                    )
        else:
            # Detect from mic
            mic_program = request.args.get("mic_program") or wake_pipeline.mic
            assert mic_program, "Missing program for mic"

            _LOGGER.debug("detect: mic=%s, wake=%s", mic_program, wake_program)

            async with (
                await create_process(rhasspy, MIC_DOMAIN, mic_program)
            ) as mic_proc:
                assert mic_proc.stdout is not None
                detection = await detect(rhasspy, wake_program, mic_proc.stdout)

        _LOGGER.debug("wake: detection=%s", detection)
        return jsonify(detection.event().to_dict() if detection is not None else {})

    @app.websocket("/wake/detect")
    async def ws_wake_detect():
        """Detect wake word in websocket audio stream."""
        wake_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        wake_program = websocket.args.get("wake_program") or wake_pipeline.wake
        assert wake_program, "Missing program for wake"

        rate = int(websocket.args.get("rate", DEFAULT_IN_RATE))
        width = int(websocket.args.get("width", DEFAULT_IN_WIDTH))
        channels = int(websocket.args.get("channels", DEFAULT_IN_CHANNELS))

        _LOGGER.debug("detect: wake=%s", wake_program)

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

        detection = await detect_stream(
            rhasspy, wake_program, audio_stream(), rate, width, channels
        )

        _LOGGER.debug("detect: detection='%s'", detection)

        await websocket.send_json(
            detection.event().to_dict() if detection is not None else {}
        )
