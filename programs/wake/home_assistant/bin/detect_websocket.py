#!/usr/bin/env python3
"""Streams audio over websocket to Home Assistant for wake word detection."""
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
    AudioChunk,
    AudioChunkConverter,
    AudioStop,
)
from rhasspy3.event import (
    Event,
    async_get_stdin,
    async_read_event,
    async_write_event,
    write_event,
)
from rhasspy3.wake import Detection

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--token", required=True, help="Home Assistant authorization token"
    )
    parser.add_argument(
        "--entity-id", help="Id of Home Assistant wake word detection entity"
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
        "--debug",
        action="store_true",
        help="Print DEBUG messages to console",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    stdin_reader = await async_get_stdin()

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

            # Register binary handler
            _LOGGER.debug("Starting detection")
            message_id = 1
            detect_args = {
                "type": "wake_word/detect",
                "id": message_id,
            }
            if args.entity_id:
                detect_args["entity_id"] = args.entity_id
            await websocket.send_json(detect_args)
            message_id += 1

            msg = await websocket.receive_json()
            _LOGGER.debug(msg)
            assert msg["success"], "Failed to start detection"

            # Get handler id.
            # This is a single byte prefix that needs to be in every binary payload.
            msg = await websocket.receive_json()
            _LOGGER.debug(msg)
            handler_id = bytes([msg["event"]["handler_id"]])

            # Detect wakeword(s)
            _LOGGER.debug("Starting detection")
            mic_task = asyncio.create_task(async_read_event(stdin_reader))
            wake_task = asyncio.create_task(websocket.receive_json())
            pending = {mic_task, wake_task}

            try:
                while True:
                    done, pending = await asyncio.wait(
                        pending, return_when=asyncio.FIRST_COMPLETED
                    )

                    if mic_task in done:
                        event = mic_task.result()
                        if (event is None) or AudioStop.is_type(event.type):
                            break

                        if AudioChunk.is_type(event.type):
                            chunk = chunk_converter.convert(
                                AudioChunk.from_event(event)
                            )

                            # Prefix binary message with handler id
                            await websocket.send_bytes(handler_id + chunk.audio)

                        # Next audio event
                        mic_task = asyncio.create_task(async_read_event(stdin_reader))
                        pending.add(mic_task)

                    if wake_task in done:
                        result_json = wake_task.result()
                        _LOGGER.info(result_json)
                        write_event(
                            Detection(
                                name=result_json["event"]["ww_id"],
                                timestamp=result_json.get("timestamp"),
                            ).event()
                        )
            finally:
                for task in pending:
                    task.cancel()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
