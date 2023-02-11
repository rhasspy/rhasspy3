#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from websockets import connect
from websockets.exceptions import ConnectionClosedOK

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.event import Event, read_event, write_event

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("uri")
    args = parser.parse_args()

    async with connect(args.uri) as websocket:
        recv_task = asyncio.create_task(websocket.recv())
        pending = {recv_task}

        while True:
            mic_event = read_event()
            if mic_event is None:
                break

            if not AudioChunk.is_type(mic_event.type):
                continue

            mic_chunk = AudioChunk.from_event(mic_event)
            send_task = asyncio.create_task(websocket.send(mic_chunk.audio))
            pending.add(send_task)

            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            if recv_task in done:
                for task in pending:
                    task.cancel()
                break

            if send_task not in done:
                await send_task

        try:
            while True:
                start: Optional[AudioStart] = None
                data = await websocket.recv()
                try:
                    event = Event.from_dict(json.loads(data))
                    if AudioStart.is_type(event.type):
                        start = AudioStart.from_event(event)
                        break
                except Exception:
                    continue

            assert start is not None

            while True:
                data = await websocket.recv()
                if isinstance(data, bytes):
                    write_event(
                        AudioChunk(
                            start.rate,
                            start.width,
                            start.channels,
                            data,
                        ).event()
                    )
                else:
                    try:
                        event = Event.from_dict(json.loads(data))
                        if AudioStop.is_type(event.type):
                            break
                    except Exception:
                        pass
        except ConnectionClosedOK:
            pass
        finally:
            write_event(AudioStop().event())


async def play(websocket, done_event: asyncio.Event):
    try:
        while True:
            audio_bytes = await websocket.recv()
            if isinstance(audio_bytes, bytes):
                done_event.set()
                sys.stdout.buffer.write(audio_bytes)
                sys.stdout.buffer.flush()
    except ConnectionClosedOK:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
