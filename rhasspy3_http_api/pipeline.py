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
        asr_chunks_to_buffer = int(
            request.args.get("asr_chunks_to_buffer", args.asr_chunks_to_buffer)
        )

        _LOGGER.debug(
            "listen-for-command: mic=%s, wake=%s, vad=%s, asr=%s, intent=%s",
            mic_program,
            wake_program,
            vad_program,
            asr_program,
            intent_program,
        )

        if asr_chunks_to_buffer > 0:
            chunk_buffer: Optional[Deque[Event]] = deque(maxlen=asr_chunks_to_buffer)
        else:
            chunk_buffer = None

        data = {}
        async with (await create_process(rhasspy, MIC_DOMAIN, mic_program)) as mic_proc:
            assert mic_proc.stdout is not None

            asr_proc = await create_process(rhasspy, ASR_DOMAIN, asr_program)
            assert asr_proc.stdin is not None
            assert asr_proc.stdout is not None

            detect_result = await detect(
                rhasspy, wake_program, mic_proc.stdout, chunk_buffer
            )
            if detect_result is not None:
                _LOGGER.debug("listen-for-command: detect=%s", detect_result)
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

                    if Transcript.is_type(asr_event.type):
                        transcript = Transcript.from_event(asr_event)
                        _LOGGER.debug("listen-for-command: transcript=%s", transcript)

                        if transcript.text:
                            recognize_result = await recognize(
                                rhasspy, intent_program, transcript.text
                            )
                            _LOGGER.debug(
                                "listen-for-command: recognize=%s", recognize_result
                            )
                            if isinstance(recognize_result, Intent):
                                data = recognize_result.to_rhasspy()
                        break

        return jsonify(data)

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
