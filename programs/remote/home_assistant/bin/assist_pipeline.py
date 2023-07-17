#!/usr/bin/env python3
"""Runs an Assist pipeline to handle audio remotely."""
import argparse
import asyncio
import logging
import shlex
import tempfile
import wave
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

import aiohttp

from rhasspy3.audio import (
    DEFAULT_SAMPLES_PER_CHUNK,
    AudioChunk,
    AudioChunkConverter,
    AudioStart,
    AudioStop,
    wav_to_chunks,
)
from rhasspy3.event import (
    Event,
    async_read_event,
    async_write_event,
    read_event,
    write_event,
)
from rhasspy3.vad import VoiceStarted, VoiceStopped

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--token", required=True, help="Home Assistant authorization token"
    )
    parser.add_argument(
        "--pipeline", help="Name of assist pipeline to use (default: preferred)"
    )
    parser.add_argument(
        "--server", default="localhost:8123", help="host:port of Home Assistant server"
    )
    parser.add_argument(
        "--server-protocol",
        default="http",
        choices=("http", "https"),
    )
    #
    parser.add_argument(
        "--audio-converter",
        default="ffmpeg -y -i {url} {file}",
        help="Program to run to convert URL to WAV file",
    )
    #
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print DEBUG messages to console",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    try:
        while True:
            # Wait for audio start
            start_event = read_event()
            assert start_event is not None

            if AudioStart.is_type(start_event.type):
                break

        _LOGGER.debug("Receiving audio")
        await run_pipeline(args)
    except KeyboardInterrupt:
        pass


async def run_pipeline(args: argparse.Namespace):
    url = f"ws://{args.server}/api/websocket"
    chunk_converter = AudioChunkConverter(rate=16000, width=2, channels=1)

    # Connect to Home Assistant
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as websocket:
            # Authenticate
            _LOGGER.debug("Authenticating")
            msg = await websocket.receive_json()
            assert msg["type"] == "auth_required", msg

            await websocket.send_json(
                {
                    "type": "auth",
                    "access_token": args.token,
                }
            )

            msg = await websocket.receive_json()
            _LOGGER.debug(msg)
            assert msg["type"] == "auth_ok", msg
            _LOGGER.info("Authenticated")

            # Determine pipeline id
            message_id = 1
            pipeline_id: Optional[str] = None
            if args.pipeline:
                # Get list of available pipelines and resolve name
                await websocket.send_json(
                    {
                        "type": "assist_pipeline/pipeline/list",
                        "id": message_id,
                    }
                )
                msg = await websocket.receive_json()
                _LOGGER.debug(msg)
                message_id += 1

                pipelines = msg["result"]["pipelines"]
                for pipeline in pipelines:
                    if pipeline["name"] == args.pipeline:
                        pipeline_id = pipeline["id"]
                        break

                if not pipeline_id:
                    raise ValueError(
                        f"No pipeline named {args.pipeline} in {pipelines}"
                    )

            # Run pipeline
            _LOGGER.debug("Starting pipeline")
            pipeline_args = {
                "type": "assist_pipeline/run",
                "id": message_id,
                "start_stage": "stt",
                "end_stage": "tts",
                "input": {
                    "sample_rate": 16000,
                },
            }
            if pipeline_id:
                pipeline_args["pipeline"] = pipeline_id
            await websocket.send_json(pipeline_args)
            message_id += 1

            msg = await websocket.receive_json()
            _LOGGER.debug(msg)
            assert msg["success"], "Pipeline failed to run"

            # Get handler id.
            # This is a single byte prefix that needs to be in every binary payload.
            msg = await websocket.receive_json()
            _LOGGER.debug(msg)
            handler_id = bytes(
                [msg["event"]["data"]["runner_data"]["stt_binary_handler_id"]]
            )

            # Audio loop for single pipeline run
            receive_event_task = asyncio.create_task(websocket.receive_json())
            is_running = True
            tts_url: Optional[str] = None
            while is_running:
                chunk_event = read_event()
                if chunk_event is None:
                    break

                if not AudioChunk.is_type(chunk_event.type):
                    continue

                chunk = chunk_converter.convert(AudioChunk.from_event(chunk_event))

                # Prefix binary message with handler id
                send_audio_task = asyncio.create_task(
                    websocket.send_bytes(handler_id + chunk.audio)
                )
                pending = {send_audio_task, receive_event_task}
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if receive_event_task in done:
                    event = receive_event_task.result()
                    _LOGGER.debug(event)
                    event_type = event["event"]["type"]
                    if event_type == "stt-start":
                        write_event(VoiceStarted().event())
                    elif event_type == "stt-end":
                        write_event(VoiceStopped().event())
                    elif event_type == "run-end":
                        _LOGGER.info("Pipeline finished")
                        is_running = False
                        break

                    if event_type == "error":
                        _LOGGER.error(event["event"]["data"]["message"])
                        is_running = False
                        break

                    if event_type == "tts-end":
                        # URL of text to speech audio response (relative to server)
                        tts_url = event["event"]["data"]["tts_output"]["url"]
                        is_running = False
                        break

                    receive_event_task = asyncio.create_task(websocket.receive_json())

                if send_audio_task not in done:
                    await send_audio_task

            if tts_url:
                _LOGGER.debug("Converting audio from URL: %s", tts_url)
                with tempfile.NamedTemporaryFile(mode="wb+", suffix=".wav") as wav_file:
                    convert_cmd = shlex.split(
                        args.audio_converter.format(
                            url=f"{args.server_protocol}://{args.server}{tts_url}",
                            file=wav_file.name,
                        )
                    )
                    convert_proc = await asyncio.create_subprocess_exec(
                        convert_cmd[0],
                        *convert_cmd[1:],
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await convert_proc.communicate()

                    wav_file.seek(0)
                    wav_reader: wave.Wave_read = wave.open(wav_file, "rb")
                    _LOGGER.debug(
                        "Sending TTS audio (frames=%s)", wav_reader.getnframes()
                    )
                    with wav_reader:
                        write_event(
                            AudioStart(
                                rate=wav_reader.getframerate(),
                                width=wav_reader.getsampwidth(),
                                channels=wav_reader.getnchannels(),
                            ).event()
                        )
                        for tts_chunk in wav_to_chunks(
                            wav_reader, samples_per_chunk=DEFAULT_SAMPLES_PER_CHUNK
                        ):
                            write_event(tts_chunk.event())

                    _LOGGER.debug("Finished sending TTS audio")

            # Required by satellite running code
            write_event(AudioStop().event())

            _LOGGER.info("Done")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
