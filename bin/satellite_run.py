#!/usr/bin/env python3
"""Run satellite loop."""
import argparse
import asyncio
import logging
import wave
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop, DEFAULT_SAMPLES_PER_CHUNK
from rhasspy3.core import Rhasspy
from rhasspy3.event import Event, async_read_event, async_write_event
from rhasspy3.mic import record
from rhasspy3.program import create_process
from rhasspy3.remote import DOMAIN as REMOTE_DOMAIN
from rhasspy3.snd import DOMAIN as SND_DOMAIN, play
from rhasspy3.snd import Played
from rhasspy3.vad import VoiceStarted, VoiceStopped
from rhasspy3.wake import detect

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
        "-s", "--satellite", default="default", help="Name of satellite to use"
    )
    #
    parser.add_argument(
        "--mic-program",
        help="Program to use for mic input (overrides satellite)",
    )
    parser.add_argument(
        "--wake-program",
        help="Program to use for wake word detection (overiddes satellite)",
    )
    parser.add_argument(
        "--wake-after-wav",
        help="Path to WAV file to play after each wake word detection",
    )
    parser.add_argument(
        "--remote-program",
        help="Program to use for remote communication with base station (overrides satellite)",
    )
    parser.add_argument(
        "--remote-voice-stopped-wav",
        help="Path to WAV file to play after remote reports user has stopped speaking",
    )
    parser.add_argument(
        "--snd-program",
        help="Program to use for audio output (overrides satellite)",
    )
    #
    parser.add_argument("--asr-chunks-to-buffer", type=int, default=0)
    parser.add_argument(
        "--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK
    )
    #
    parser.add_argument("--save-audio-dir", help="Directory to save wake/asr/tts audio")
    #
    parser.add_argument("--loop", action="store_true", help="Keep satellite running")
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    wake_program = args.wake_program
    remote_program = args.remote_program
    snd_program = args.snd_program
    satellite = rhasspy.config.satellites.get(args.satellite)

    if not mic_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        mic_program = satellite.mic

    assert mic_program, "No mic program"

    if not wake_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        wake_program = satellite.wake

    assert wake_program, "No wake program"

    if not remote_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        remote_program = satellite.remote

    assert remote_program, "No remote program"

    if not snd_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        snd_program = satellite.snd

    assert snd_program, "No snd program"

    if args.save_audio_dir:
        # Directory to save wav/asr/tts WAV audio for each loop
        args.save_audio_dir = Path(args.save_audio_dir)
        args.save_audio_dir.mkdir(parents=True, exist_ok=True)

    loop_idx = 0
    while True:
        chunk_buffer: Deque[Event] = deque(maxlen=args.asr_chunks_to_buffer)
        snd_buffer: List[Event] = []

        async with record(rhasspy, mic_program) as mic_proc:
            assert mic_proc.stdin is not None
            assert mic_proc.stdout is not None

            wake_wav_writer: Optional[wave.Wave_write] = None
            if args.save_audio_dir:
                # Save wake recording
                wake_wav_writer = wave.open(
                    str(args.save_audio_dir / f"{loop_idx:04}_wake.wav"), "wb"
                )

            detection = await detect(
                rhasspy,
                wake_program,
                mic_proc.stdout,
                chunk_buffer,
                save_wav_writer=wake_wav_writer,
            )
            if detection is None:
                continue

            if args.wake_after_wav:
                # Play sound after wake word detection
                with open(args.wake_after_wav, "rb") as wake_after_wav_file:
                    await play(
                        rhasspy,
                        snd_program,
                        wake_after_wav_file,
                        args.samples_per_chunk,
                    )

            asr_wav_writer: Optional[wave.Wave_write] = None
            asr_wav_writer_set = False
            if args.save_audio_dir:
                # Save ASR recording
                asr_wav_writer = wave.open(
                    str(args.save_audio_dir / f"{loop_idx:04}_asr.wav"), "wb"
                )

            async with (
                await create_process(rhasspy, REMOTE_DOMAIN, remote_program)
            ) as remote_proc:
                assert remote_proc.stdin is not None
                assert remote_proc.stdout is not None

                is_start_sent = False

                # Send chunk to remote and save if configured
                async def process_asr_chunk(chunk_event: Event):
                    nonlocal is_start_sent, asr_wav_writer_set
                    chunk: Optional[AudioChunk] = None

                    if (asr_wav_writer is not None) or (not is_start_sent):
                        # Need to decode event
                        chunk = AudioChunk.from_event(chunk_event)

                    if asr_wav_writer is not None:
                        assert chunk is not None
                        if not asr_wav_writer_set:
                            # Configure WAV
                            asr_wav_writer.setframerate(chunk.rate)
                            asr_wav_writer.setsampwidth(chunk.width)
                            asr_wav_writer.setnchannels(chunk.channels)
                            asr_wav_writer_set = True

                        asr_wav_writer.writeframes(chunk.audio)

                    if not is_start_sent:
                        # Inform remote that audio is starting
                        assert chunk is not None
                        await async_write_event(
                            AudioStart(
                                rate=chunk.rate,
                                width=chunk.width,
                                channels=chunk.channels,
                            ).event(),
                            remote_proc.stdin,
                        )
                        is_start_sent = True

                    await async_write_event(chunk_event, remote_proc.stdin)

                while chunk_buffer:
                    chunk_event = chunk_buffer.pop()
                    await process_asr_chunk(chunk_event)

                mic_task = asyncio.create_task(async_read_event(mic_proc.stdout))
                remote_task = asyncio.create_task(async_read_event(remote_proc.stdout))
                pending = {mic_task, remote_task}

                try:
                    # Stream to remote until audio is received
                    while True:
                        done, pending = await asyncio.wait(
                            pending, return_when=asyncio.FIRST_COMPLETED
                        )

                        if mic_task in done:
                            mic_event = mic_task.result()
                            if mic_event is None:
                                break

                            if AudioChunk.is_type(mic_event.type):
                                await process_asr_chunk(mic_event)

                            mic_task = asyncio.create_task(
                                async_read_event(mic_proc.stdout)
                            )
                            pending.add(mic_task)

                        if remote_task in done:
                            remote_event = remote_task.result()
                            if remote_event is None:
                                break

                            if (
                                AudioStart.is_type(remote_event.type)
                                or AudioChunk.is_type(remote_event.type)
                                or AudioStop.is_type(remote_event.type)
                            ):
                                # Remote is streaming audio back.
                                # Stop what we're doing and start playback.
                                snd_buffer.append(remote_event)

                                for task in pending:
                                    task.cancel()

                                break

                            if args.remote_voice_stopped_wav and VoiceStopped.is_type(
                                remote_event.type
                            ):
                                with open(
                                    args.remote_voice_stopped_wav, "rb"
                                ) as remote_voice_stopped_wav_file:
                                    await play(
                                        rhasspy,
                                        snd_program,
                                        remote_voice_stopped_wav_file,
                                        args.samples_per_chunk,
                                    )

                            remote_task = asyncio.create_task(
                                async_read_event(remote_proc.stdout)
                            )
                            pending.add(remote_task)

                    # Output audio
                    async with (
                        await create_process(rhasspy, SND_DOMAIN, snd_program)
                    ) as snd_proc:
                        assert snd_proc.stdin is not None
                        assert snd_proc.stdout is not None

                        tts_wav_writer: Optional[wave.Wave_write] = None
                        tts_wav_writer_set = False
                        if args.save_audio_dir:
                            # Save TTS recording
                            tts_wav_writer = wave.open(
                                str(args.save_audio_dir / f"{loop_idx:04}_tts.wav"),
                                "wb",
                            )

                        # Send to snd and save if configured
                        async def process_tts_chunk(chunk_event: Event):
                            nonlocal tts_wav_writer_set

                            if tts_wav_writer is not None:
                                chunk = AudioChunk.from_event(chunk_event)
                                if not tts_wav_writer_set:
                                    # Configure WAV
                                    tts_wav_writer.setframerate(chunk.rate)
                                    tts_wav_writer.setsampwidth(chunk.width)
                                    tts_wav_writer.setnchannels(chunk.channels)
                                    tts_wav_writer_set = True

                                tts_wav_writer.writeframes(chunk.audio)

                            await async_write_event(chunk_event, snd_proc.stdin)

                        is_stopped = False
                        has_output_audio = False
                        for remote_event in snd_buffer:
                            if AudioChunk.is_type(remote_event.type):
                                has_output_audio = True
                                await process_tts_chunk(remote_event)
                            elif AudioStop.is_type(remote_event.type):
                                # Unexpected, but it could happen
                                is_stopped = True
                                break

                        while not is_stopped:
                            remote_event = await async_read_event(remote_proc.stdout)
                            if remote_event is None:
                                break

                            if AudioChunk.is_type(remote_event.type):
                                has_output_audio = True
                                await process_tts_chunk(remote_event)
                            elif AudioStop.is_type(remote_event.type):
                                await async_write_event(remote_event, snd_proc.stdin)
                                is_stopped = True

                        if has_output_audio:
                            # Wait for audio to finish playing
                            while True:
                                snd_event = await async_read_event(snd_proc.stdout)
                                if snd_event is None:
                                    break

                                if Played.is_type(snd_event.type):
                                    break

                except Exception:
                    _LOGGER.exception(
                        "Unexpected error communicating with remote base station"
                    )

        if not args.loop:
            break

        loop_idx += 1


# -----------------------------------------------------------------------------


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
