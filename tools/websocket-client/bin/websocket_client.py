#!/usr/bin/env python3
import argparse
import asyncio
import wave
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

from websockets import connect


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("wav_file", nargs="+", help="Path(s) to WAV file(s)")
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()

    for wav_path in args.wav_file:
        wav_file: wave.Wave_read = wave.open(wav_path, "rb")
        with wav_file:
            # Add audio parameters if missing
            parse_result = urlparse(args.url)
            query = dict(parse_qsl(parse_result.query))
            query.setdefault("rate", str(wav_file.getframerate()))
            query.setdefault("width", str(wav_file.getsampwidth()))
            query.setdefault("channels", str(wav_file.getnchannels()))

            url = urlunparse(parse_result._replace(query=urlencode(query)))
            async with connect(url) as websocket:
                chunk = wav_file.readframes(args.samples_per_chunk)
                while chunk:
                    await websocket.send(chunk)
                    chunk = wav_file.readframes(args.samples_per_chunk)

                # Signal stop with empty message
                await websocket.send(bytes())
                result = await websocket.recv()
                print(result)


if __name__ == "__main__":
    asyncio.run(main())
