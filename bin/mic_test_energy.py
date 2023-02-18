#!/usr/bin/env python3
"""Prints microphone energy level to console for testing."""
import argparse
import asyncio
import audioop
import logging
from pathlib import Path

from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.program import create_process

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument(
        "-p", "--pipeline", default="default", help="Name of pipeline to use"
    )
    parser.add_argument(
        "--mic-program", help="Name of mic program to use (overrides pipeline)"
    )
    #
    parser.add_argument(
        "--levels", type=int, default=40, help="Number of levels to display"
    )
    parser.add_argument(
        "--numeric",
        action="store_true",
        help="Print energy numeric values instead of showing level",
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not mic_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        mic_program = pipeline.mic

    assert mic_program, "No mic program"
    max_energy = 0

    async with (await create_process(rhasspy, MIC_DOMAIN, mic_program)) as mic_proc:
        assert mic_proc.stdout is not None

        while True:
            event = await async_read_event(mic_proc.stdout)
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                energy = -audioop.rms(chunk.audio, chunk.width)
                energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
                debiased_energy = audioop.rms(
                    audioop.add(
                        chunk.audio,
                        energy_bytes * (len(chunk.audio) // chunk.width),
                        chunk.width,
                    ),
                    chunk.width,
                )

                max_energy = max(max_energy, debiased_energy)
                max_energy = max(1, max_energy)

                if args.numeric:
                    # Print numbers
                    print(debiased_energy, "/", max_energy)
                else:
                    # Print graphic
                    energy_level = int(args.levels * (debiased_energy / max_energy))
                    energy_level = max(0, energy_level)
                    print(
                        "\r",  # We still use typewriters!
                        "[",
                        "*" * energy_level,
                        " " * (args.levels - energy_level),
                        "]",
                        sep="",
                        end="",
                    )

            elif AudioStop.is_type(event.type):
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
