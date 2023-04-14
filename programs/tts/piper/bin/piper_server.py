#!/usr/bin/env python3
import argparse
import logging
import math
import os
import json
import socket
import subprocess
import tempfile
import wave
from pathlib import Path

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import read_event, write_event
from wyoming.tts import Synthesize
from wyoming.info import Describe, TtsProgram, TtsVoice, Attribution, Info, Describe

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to model file (.onnx)")
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument(
        "--auto-punctuation", default=".?!", help="Automatically add punctuation"
    )
    parser.add_argument(
        "--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK
    )
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Load voice info
    voice_config_path = f"{args.model}.json"
    with open(voice_config_path, "r", encoding="utf-8") as voice_config_file:
        voice_config = json.load(voice_config_file)

    model_language = voice_config["espeak"]["voice"]
    model_path = Path(args.model)
    wyoming_info = Info(
        asr=[],
        tts=[
            TtsProgram(
                name="piper",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/piper"
                ),
                installed=True,
                voices=[
                    TtsVoice(
                        name=model_path.stem,
                        attribution=Attribution(
                            name="rhasspy", url="https://github.com/rhasspy/piper"
                        ),
                        installed=True,
                        languages=[model_language],
                    )
                ],
            )
        ],
    )

    is_unix = args.uri.startswith("unix://")
    is_tcp = args.uri.startswith("tcp://")

    assert is_unix or is_tcp, "Only unix:// or tcp:// are supported"
    if is_unix:
        args.uri = args.uri[len("unix://") :]
    elif is_tcp:
        args.uri = args.uri[len("tcp://") :]

    if is_unix:
        # Need to unlink socket if it exists
        try:
            os.unlink(args.uri)
        except OSError:
            pass

    try:
        # Create socket server
        if is_unix:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(args.uri)
            _LOGGER.info("Unix socket at %s", args.uri)
        else:
            address, port_str = args.uri.split(":", maxsplit=1)
            port = int(port_str)
            sock = socket.create_server((address, port))
            _LOGGER.info("TCP server at %s", args.uri)

        sock.listen()

        with tempfile.TemporaryDirectory() as temp_dir:
            command = [
                str(_DIR / "piper"),
                "--model",
                str(args.model),
                "--output_dir",
                temp_dir,
            ]
            with subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
            ) as proc:
                _LOGGER.info("Ready")

                # Listen for connections
                while True:
                    try:
                        connection, client_address = sock.accept()
                        _LOGGER.debug("Connection from %s", client_address)
                        handle_connection(connection, proc, args, wyoming_info)
                    except KeyboardInterrupt:
                        break
                    except Exception:
                        _LOGGER.exception("Error communicating with socket client")
    finally:
        if is_unix:
            os.unlink(args.uri)


def handle_connection(
    connection: socket.socket,
    proc: subprocess.Popen,
    args: argparse.Namespace,
    wyoming_info: Info,
) -> None:
    assert proc.stdin is not None
    assert proc.stdout is not None

    with connection, connection.makefile(mode="rwb") as conn_file:
        while True:
            event = read_event(conn_file)
            if event is None:
                _LOGGER.error("Empty event from client")
                break

            if Describe.is_type(event.type):
                write_event(wyoming_info.event(), conn_file)
                _LOGGER.debug("Sent info")
                continue

            if not Synthesize.is_type(event.type):
                _LOGGER.warning("Unexpected event: %s", event)
                continue

            synthesize = Synthesize.from_event(event)
            raw_text = synthesize.text
            text = raw_text.strip()
            if args.auto_punctuation and text:
                has_punctuation = False
                for punc_char in args.auto_punctuation:
                    if text[-1] == punc_char:
                        has_punctuation = True
                        break

                if not has_punctuation:
                    text = text + args.auto_punctuation[0]

            _LOGGER.debug("synthesize: raw_text=%s, text='%s'", raw_text, text)

            # Text in, file path out
            print(text.strip(), file=proc.stdin, flush=True)
            output_path = proc.stdout.readline().strip()
            _LOGGER.debug(output_path)

            wav_file: wave.Wave_read = wave.open(output_path, "rb")
            with wav_file:
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()

                write_event(
                    AudioStart(
                        rate=rate,
                        width=width,
                        channels=channels,
                    ).event(),
                    conn_file,
                )

                # Audio
                audio_bytes = wav_file.readframes(wav_file.getnframes())
                bytes_per_sample = width * channels
                bytes_per_chunk = bytes_per_sample * args.samples_per_chunk
                num_chunks = int(math.ceil(len(audio_bytes) / bytes_per_chunk))

                # Split into chunks
                for i in range(num_chunks):
                    offset = i * bytes_per_chunk
                    chunk = audio_bytes[offset : offset + bytes_per_chunk]
                    write_event(
                        AudioChunk(
                            audio=chunk,
                            rate=rate,
                            width=width,
                            channels=channels,
                        ).event(),
                        conn_file,
                    )

            write_event(AudioStop().event(), conn_file)
            _LOGGER.debug("Completed request")

            os.unlink(output_path)
            break


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
