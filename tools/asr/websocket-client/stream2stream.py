#!/usr/bin/env python3
import argparse
import asyncio
import sys
import wave

from websockets import connect
from websockets.exceptions import ConnectionClosedOK


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("uri")
    parser.add_argument("wav_file", nargs="+", help="Path(s) to WAV file(s)")
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()

    for wav_path in args.wav_file:
        with wave.open(wav_path, "rb") as wav_file:
            async with connect(args.uri) as websocket:
                task = asyncio.create_task(play(websocket))
                chunk = wav_file.readframes(args.samples_per_chunk)
                while chunk:
                    await websocket.send(chunk)
                    chunk = wav_file.readframes(args.samples_per_chunk)

                await websocket.send(bytes())
                await websocket.wait_closed()
                await task


async def play(websocket):
    try:
        while True:
            audio_bytes = await websocket.recv()
            if isinstance(audio_bytes, bytes):
                sys.stdout.buffer.write(audio_bytes)
                sys.stdout.buffer.flush()
    except ConnectionClosedOK:
        pass


if __name__ == "__main__":
    asyncio.run(main())
