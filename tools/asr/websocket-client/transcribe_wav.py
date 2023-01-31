#!/usr/bin/env python3
import argparse
import asyncio
import wave

from websockets import connect


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("uri")
    parser.add_argument("wav_file", nargs="+", help="Path(s) to WAV file(s)")
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()

    for wav_path in args.wav_file:
        with wave.open(wav_path, "rb") as wav_file:
            async with connect(args.uri) as websocket:
                chunk = wav_file.readframes(args.samples_per_chunk)
                while chunk:
                    await websocket.send(chunk)
                    chunk = wav_file.readframes(args.samples_per_chunk)

                await websocket.send(bytes())
                result = await websocket.recv()
                print(result)


if __name__ == "__main__":
    asyncio.run(main())
