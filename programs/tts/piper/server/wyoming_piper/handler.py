"""Event handler for clients of the server."""
import argparse
import json
import logging
import math
import os
import wave
from typing import Any, Dict, Optional

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.tts import Synthesize

from .process import PiperProcessManager

_LOGGER = logging.getLogger(__name__)


class PiperEventHandler(AsyncEventHandler):
    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        process_manager: PiperProcessManager,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.wyoming_info_event = wyoming_info.event()
        self.process_manager = process_manager

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info")
            return True

        if not Synthesize.is_type(event.type):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        synthesize = Synthesize.from_event(event)
        _LOGGER.debug(synthesize)

        raw_text = synthesize.text

        # Join multiple lines
        text = " ".join(raw_text.strip().splitlines())

        if self.cli_args.auto_punctuation and text:
            # Add automatic punctuation (important for some voices)
            has_punctuation = False
            for punc_char in self.cli_args.auto_punctuation:
                if text[-1] == punc_char:
                    has_punctuation = True
                    break

            if not has_punctuation:
                text = text + self.cli_args.auto_punctuation[0]

        async with self.process_manager.processes_lock:
            _LOGGER.debug("synthesize: raw_text=%s, text='%s'", raw_text, text)
            voice_name: Optional[str] = None
            voice_speaker: Optional[str] = None
            if synthesize.voice is not None:
                voice_name = synthesize.voice.name
                voice_speaker = synthesize.voice.speaker

            piper_proc = await self.process_manager.get_process(voice_name=voice_name)

            assert piper_proc.proc.stdin is not None
            assert piper_proc.proc.stdout is not None

            # JSON in, file path out
            input_obj: Dict[str, Any] = {"text": text}
            if voice_speaker is not None:
                speaker_id = piper_proc.get_speaker_id(voice_speaker)
                if speaker_id is not None:
                    input_obj["speaker_id"] = speaker_id
                else:
                    _LOGGER.warning(
                        "No speaker '%s' for voice '%s'", voice_speaker, voice_name
                    )

            _LOGGER.debug("input: %s", input_obj)
            piper_proc.proc.stdin.write(
                (json.dumps(input_obj, ensure_ascii=False) + "\n").encode()
            )
            await piper_proc.proc.stdin.drain()

            output_path = (await piper_proc.proc.stdout.readline()).decode().strip()
            _LOGGER.debug(output_path)

        wav_file: wave.Wave_read = wave.open(output_path, "rb")
        with wav_file:
            rate = wav_file.getframerate()
            width = wav_file.getsampwidth()
            channels = wav_file.getnchannels()

            await self.write_event(
                AudioStart(
                    rate=rate,
                    width=width,
                    channels=channels,
                ).event(),
            )

            # Audio
            audio_bytes = wav_file.readframes(wav_file.getnframes())
            bytes_per_sample = width * channels
            bytes_per_chunk = bytes_per_sample * self.cli_args.samples_per_chunk
            num_chunks = int(math.ceil(len(audio_bytes) / bytes_per_chunk))

            # Split into chunks
            for i in range(num_chunks):
                offset = i * bytes_per_chunk
                chunk = audio_bytes[offset : offset + bytes_per_chunk]
                await self.write_event(
                    AudioChunk(
                        audio=chunk,
                        rate=rate,
                        width=width,
                        channels=channels,
                    ).event(),
                )

        await self.write_event(AudioStop().event())
        _LOGGER.debug("Completed request")

        os.unlink(output_path)

        return True
