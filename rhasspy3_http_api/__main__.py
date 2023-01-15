import asyncio
import argparse
import logging
import io
import wave
from typing import Optional, Tuple
from uuid import uuid4

import hypercorn
import quart_cors
from quart import (
    Quart,
    Response,
    jsonify,
    request,
)

from rhasspy3.asr import DOMAIN as ASR_DOMAIN, Transcript
from rhasspy3.core import Rhasspy
from rhasspy3.audio import wav_to_chunks, AudioStart, AudioStop
from rhasspy3.snd import DOMAIN as SND_DOMAIN
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.program import create_process

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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    pipeline = rhasspy.config.pipelines[args.pipeline]

    app = Quart("rhasspy3")
    app.secret_key = str(uuid4())
    app = quart_cors.cors(app)

    @app.errorhandler(Exception)
    async def handle_error(err) -> Tuple[str, int]:
        """Return error as text."""
        _LOGGER.exception(err)
        return (f"{err.__class__.__name__}: {err}", 500)

    @app.route("/api/play-wav", methods=["POST"])
    async def api_play_wav() -> str:
        wav_bytes = await request.data
        with io.BytesIO(wav_bytes) as wav_io:
            wav_file: wave.Wave_read = wave.open(wav_io, "rb")
            with wav_file:
                snd_proc = await create_process(rhasspy, SND_DOMAIN, pipeline.snd)
                assert snd_proc.stdin is not None

                for chunk in wav_to_chunks(wav_file, samples_per_chunk=1024):
                    await async_write_event(chunk.event(), snd_proc.stdin)

        return str(len(wav_bytes))

    @app.route("/api/speech-to-text", methods=["POST"])
    async def api_speech_to_text() -> str:
        wav_bytes = await request.data
        with io.BytesIO(wav_bytes) as wav_io:
            wav_file: wave.Wave_read = wave.open(wav_io, "rb")
            with wav_file:
                asr_proc = await create_process(rhasspy, ASR_DOMAIN, pipeline.asr)
                assert asr_proc.stdin is not None
                assert asr_proc.stdout is not None

                timestamp = 0
                await async_write_event(
                    AudioStart(timestamp=timestamp).event(), asr_proc.stdin
                )

                for chunk in wav_to_chunks(wav_file, samples_per_chunk=1024):
                    await async_write_event(chunk.event(), asr_proc.stdin)
                    if chunk.timestamp is not None:
                        timestamp = chunk.timestamp
                    else:
                        timestamp += chunk.milliseconds

                await async_write_event(
                    AudioStop(timestamp=timestamp).event(), asr_proc.stdin
                )

                transcript: Optional[Transcript] = None
                while True:
                    event = await async_read_event(asr_proc.stdout)
                    if event is None:
                        break

                    if Transcript.is_type(event.type):
                        transcript = Transcript.from_event(event)
                        break

                if transcript is not None:
                    return transcript.text

        return ""

    hyp_config = hypercorn.config.Config()
    hyp_config.bind = [f"{args.host}:{args.port}"]

    try:
        asyncio.run(hypercorn.asyncio.serve(app, hyp_config))
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
