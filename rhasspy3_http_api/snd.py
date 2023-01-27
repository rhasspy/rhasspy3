import argparse
import io
import logging

from quart import request, Quart

from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.snd import play

_LOGGER = logging.getLogger(__name__)


def add_snd(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/api/play-wav", methods=["POST"])
    async def api_play_wav() -> str:
        wav_bytes = await request.data
        program = request.args.get("program", pipeline.snd)
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )

        _LOGGER.debug("play-wav: snd=%s, wav=%s byte(s)", program, len(wav_bytes))

        with io.BytesIO(wav_bytes) as wav_in:
            await play(rhasspy, program, wav_in, samples_per_chunk, sleep=True)

        return str(len(wav_bytes))
