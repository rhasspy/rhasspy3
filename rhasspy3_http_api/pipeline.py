import argparse
import asyncio
import logging
from collections import deque
from typing import Optional, Deque

from quart import request, Quart, Response, jsonify, websocket

from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    DEFAULT_OUT_CHANNELS,
    DEFAULT_OUT_RATE,
    DEFAULT_OUT_WIDTH,
)
from rhasspy3.asr import DOMAIN as ASR_DOMAIN, Transcript, transcribe_stream
from rhasspy3.audio import AudioChunkConverter
from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.event import Event, async_read_event
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.program import create_process
from rhasspy3.intent import recognize, Intent
from rhasspy3.wake import detect
from rhasspy3.vad import segment
from rhasspy3.tts import synthesize_stream
from rhasspy3.pipeline import run as run_pipeline, StopAfterDomain

_LOGGER = logging.getLogger(__name__)


def add_pipeline(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/api/listen-for-command", methods=["GET", "POST"])
    async def api_listen_for_command() -> Response:
        mic_program = request.args.get("mic_program", pipeline.mic)
        wake_program = request.args.get("wake_program", pipeline.wake)
        vad_program = request.args.get("vad_program", pipeline.vad)
        asr_program = request.args.get("asr_program", pipeline.asr)
        intent_program = request.args.get("intent_program", pipeline.intent)
        handle_program = request.args.get("handle_program", pipeline.handle)
        tts_program = request.args.get("tts_program", pipeline.tts)
        snd_program = request.args.get("snd_program", pipeline.snd)
        #
        stop_after = request.args.get("stop_after")
        #
        samples_per_chunk = int(
            request.args.get("samples_per_chunk", args.samples_per_chunk)
        )
        asr_chunks_to_buffer = int(
            request.args.get("asr_chunks_to_buffer", args.asr_chunks_to_buffer)
        )

        _LOGGER.debug(
            "listen-for-command:"
            + "mic=%s,"
            + "wake=%s,"
            + "vad=%s,"
            + "asr=%s,"
            + "intent=%s,"
            + "handle=%s,"
            + "tts=%s,"
            + "snd=%s,"
            + "stop_after=%s",
            mic_program,
            wake_program,
            vad_program,
            asr_program,
            intent_program,
            handle_program,
            tts_program,
            snd_program,
            stop_after,
        )

        pipeline_result = await run_pipeline(
            rhasspy,
            pipeline,
            samples_per_chunk,
            asr_chunks_to_buffer=asr_chunks_to_buffer,
            mic_program=mic_program,
            wake_program=wake_program,
            asr_program=asr_program,
            vad_program=vad_program,
            intent_program=intent_program,
            handle_program=handle_program,
            tts_program=tts_program,
            snd_program=snd_program,
            stop_after=stop_after,
        )

        return jsonify(pipeline_result.to_dict())

    @app.websocket("/api/stream-to-stream")
    async def api_stream_to_stream():
        asr_program = websocket.args.get("asr_program", pipeline.asr)
        assert asr_program, "Missing program for asr"
        _LOGGER.debug("speech-to-text: asr=%s", asr_program)

        tts_program = websocket.args.get("tts_program", pipeline.tts)
        assert tts_program, "Missing program for tts"
        _LOGGER.debug("speech-to-text: tts=%s", tts_program)

        in_rate = int(websocket.args.get("in_rate", DEFAULT_IN_RATE))
        in_width = int(websocket.args.get("in_width", DEFAULT_IN_WIDTH))
        in_channels = int(websocket.args.get("in_channels", DEFAULT_IN_CHANNELS))

        out_rate = int(websocket.args.get("out_rate", DEFAULT_OUT_RATE))
        out_width = int(websocket.args.get("out_width", DEFAULT_OUT_WIDTH))
        out_channels = int(websocket.args.get("out_channels", DEFAULT_OUT_CHANNELS))

        async def audio_stream():
            while True:
                audio_bytes = await websocket.receive()
                if not audio_bytes:
                    yield bytes()
                    break

                if isinstance(audio_bytes, bytes):
                    yield audio_bytes

        transcript = await transcribe_stream(
            rhasspy, asr_program, audio_stream(), in_rate, in_width, in_channels
        )

        # TODO: intent, handle

        converter = AudioChunkConverter(out_rate, out_width, out_channels)
        async for chunk in synthesize_stream(rhasspy, tts_program, transcript.text):
            chunk = converter.convert(chunk)
            await websocket.send(chunk.audio)
