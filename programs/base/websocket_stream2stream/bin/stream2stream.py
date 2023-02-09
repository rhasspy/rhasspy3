#!/usr/bin/env python3
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from websockets import connect
from websockets.exceptions import ConnectionClosedOK

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("uri")
    parser.add_argument(
        "--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK
    )
    args = parser.parse_args()

    async with connect(args.uri) as websocket:
        recv_task = asyncio.create_task(websocket.recv())
        pending = {recv_task}

        while True:
            mic_chunk = sys.stdin.buffer.read(args.samples_per_chunk)
            send_task = asyncio.create_task(websocket.send(mic_chunk))
            pending.add(send_task)

            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            if recv_task in done:
                break

            if send_task not in done:
                await send_task

        try:
            while True:
                snd_chunk = await websocket.recv()
                if isinstance(snd_chunk, bytes):
                    sys.stdout.buffer.write(snd_chunk)
                    sys.stdout.buffer.flush()
        except ConnectionClosedOK:
            pass


async def stop(websocket, done_event: asyncio.Event):
    try:
        while True:
            message = await websocket.recv()
            assert False, message
            if message == "stop":
                break
    finally:
        done_event.set()


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
