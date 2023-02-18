#!/usr/bin/env python3
"""Record a spoken audio sample to a WAV file."""
import argparse
import asyncio
import logging
import wave
from collections import deque
from pathlib import Path
from typing import Deque

from rhasspy3.audio import AudioChunk
from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.program import create_process
from rhasspy3.vad import DOMAIN as VAD_DOMAIN
from rhasspy3.vad import VoiceStarted, VoiceStopped

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to write")
    #
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
    parser.add_argument(
        "--vad-program", help="Name of vad program to use (overrides pipeline)"
    )
    #
    parser.add_argument(
        "--chunk-buffer-size",
        type=int,
        default=25,
        help="Audio chunks to buffer before start is known",
    )
    parser.add_argument(
        "-b",
        "--keep-chunks-before",
        type=int,
        default=5,
        help="Audio chunks to keep before voice starts",
    )
    parser.add_argument(
        "-a",
        "--keep-chunks-after",
        type=int,
        default=0,
        help="Audio chunks to keep after voice ends",
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    vad_program = args.vad_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not mic_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        mic_program = pipeline.mic

    assert mic_program, "No mic program"

    if not vad_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        vad_program = pipeline.vad

    assert vad_program, "No vad program"

    for wav_path in args.wav_file:
        wav_file: wave.Wave_write = wave.open(wav_path, "wb")
        with wav_file:
            is_first_chunk = True

            # Audio kept before we get the event that the voice command started
            # at a timestep in the past.
            chunk_buffer: Deque[AudioChunk] = deque(
                maxlen=max(args.chunk_buffer_size, args.keep_chunks_before)
            )

            async with (
                await create_process(rhasspy, MIC_DOMAIN, mic_program)
            ) as mic_proc, (
                await create_process(rhasspy, VAD_DOMAIN, vad_program)
            ) as vad_proc:
                assert mic_proc.stdout is not None
                assert vad_proc.stdin is not None
                assert vad_proc.stdout is not None

                _LOGGER.info("Recording %s", wav_path)
                mic_task = asyncio.create_task(async_read_event(mic_proc.stdout))
                vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
                pending = {mic_task, vad_task}

                before_command = True
                while True:
                    done, pending = await asyncio.wait(
                        pending, return_when=asyncio.FIRST_COMPLETED
                    )
                    if mic_task in done:
                        mic_event = mic_task.result()
                        if mic_event is None:
                            break

                        # Process chunk
                        if AudioChunk.is_type(mic_event.type):
                            chunk = AudioChunk.from_event(mic_event)
                            if is_first_chunk:
                                _LOGGER.debug("Receiving audio")
                                is_first_chunk = False
                                wav_file.setframerate(chunk.rate)
                                wav_file.setsampwidth(chunk.width)
                                wav_file.setnchannels(chunk.channels)

                            await async_write_event(mic_event, vad_proc.stdin)
                            if before_command:
                                chunk_buffer.append(chunk)
                            else:
                                wav_file.writeframes(chunk.audio)

                        # Next chunk
                        mic_task = asyncio.create_task(
                            async_read_event(mic_proc.stdout)
                        )
                        pending.add(mic_task)

                    if vad_task in done:
                        vad_event = vad_task.result()
                        if vad_event is None:
                            break

                        if VoiceStarted.is_type(vad_event.type):
                            if before_command:
                                # Start of voice command
                                voice_started = VoiceStarted.from_event(vad_event)
                                if voice_started.timestamp is None:
                                    # Keep chunks before
                                    chunks_left = args.keep_chunks_before
                                    while chunk_buffer and (chunks_left > 0):
                                        chunk = chunk_buffer.popleft()
                                        wav_file.writeframes(chunk.audio)
                                else:
                                    # Locate start chunk
                                    start_idx = 0
                                    for i, chunk in enumerate(chunk_buffer):
                                        if (chunk.timestamp is not None) and (
                                            chunk.timestamp >= voice_started.timestamp
                                        ):
                                            start_idx = i
                                            break

                                    # Back up by "keep chunks" and then write audio forward
                                    start_idx = max(
                                        0, start_idx - args.keep_chunks_before
                                    )
                                    for i, chunk in enumerate(chunk_buffer):
                                        if i >= start_idx:
                                            wav_file.writeframes(chunk.audio)

                                    chunk_buffer.clear()

                                before_command = False
                                _LOGGER.info("Speaking started")
                        elif VoiceStopped.is_type(vad_event.type):
                            # End of voice command
                            _LOGGER.info("Speaking ended")
                            break

                        # Next VAD event
                        vad_task = asyncio.create_task(
                            async_read_event(vad_proc.stdout)
                        )
                        pending.add(vad_task)

                # After chunks
                num_chunks_left = args.keep_chunks_after
                while num_chunks_left > 0:
                    mic_event = await mic_task
                    if mic_event is None:
                        break

                    if AudioChunk.is_type(mic_event.type):
                        chunk = AudioChunk.from_event(mic_event)
                        wav_file.writeframes(chunk.audio)
                        num_chunks_left -= 1

                    if num_chunks_left > 0:
                        mic_task = asyncio.create_task(
                            async_read_event(mic_proc.stdout)
                        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
