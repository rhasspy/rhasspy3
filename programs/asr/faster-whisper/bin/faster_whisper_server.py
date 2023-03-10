#!/usr/bin/env python3
import argparse
import io
import logging
import os
import socket
import wave
from pathlib import Path

from faster_whisper import WhisperModel

from rhasspy3.asr import Transcript
from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.event import read_event, write_event

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to faster-whisper model directory")
    parser.add_argument(
        "--socketfile", required=True, help="Path to Unix domain socket file"
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device to use for inference (default: cpu)",
    )
    parser.add_argument(
        "--language",
        help="Language to set for transcription",
    )
    parser.add_argument(
        "--compute-type",
        default="default",
        help="Compute type (float16, int8, etc.)",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=1,
    )
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Need to unlink socket if it exists
    try:
        os.unlink(args.socketfile)
    except OSError:
        pass

    try:
        # Create socket server
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(args.socketfile)
        sock.listen()

        # Load converted faster-whisper model
        model = WhisperModel(
            args.model, device=args.device, compute_type=args.compute_type
        )
        _LOGGER.info("Ready")

        # Listen for connections
        while True:
            try:
                connection, client_address = sock.accept()
                _LOGGER.debug("Connection from %s", client_address)

                is_first_audio = True
                with connection, connection.makefile(
                    mode="rwb"
                ) as conn_file, io.BytesIO() as wav_io:
                    wav_file: wave.Wave_write = wave.open(wav_io, "wb")
                    with wav_file:
                        while True:
                            event = read_event(conn_file)  # type: ignore
                            if event is None:
                                break

                            if AudioChunk.is_type(event.type):
                                chunk = AudioChunk.from_event(event)

                                if is_first_audio:
                                    _LOGGER.debug("Receiving audio")
                                    wav_file.setframerate(chunk.rate)
                                    wav_file.setsampwidth(chunk.width)
                                    wav_file.setnchannels(chunk.channels)
                                    is_first_audio = False

                                wav_file.writeframes(chunk.audio)
                            elif AudioStop.is_type(event.type):
                                _LOGGER.debug("Audio stopped")
                                break

                    wav_io.seek(0)
                    segments, _info = model.transcribe(
                        wav_io,
                        beam_size=args.beam_size,
                        language=args.language,
                    )
                    text = " ".join(segment.text for segment in segments)
                    _LOGGER.info(text)

                    write_event(Transcript(text=text).event(), conn_file)  # type: ignore
            except KeyboardInterrupt:
                break
            except Exception:
                _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
