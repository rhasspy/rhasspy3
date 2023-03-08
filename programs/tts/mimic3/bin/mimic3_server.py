#!/usr/bin/env python3
import argparse
import json
import logging
import os
import socket
import threading
from pathlib import Path

from mimic3_tts import (
    DEFAULT_VOICE,
    AudioResult,
    Mimic3Settings,
    Mimic3TextToSpeechSystem,
)

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("voices_dir", help="Path to directory with <language>/<voice>")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Name of voice to use")
    parser.add_argument(
        "--socketfile", required=True, help="Path to Unix domain socket file"
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

        mimic3 = Mimic3TextToSpeechSystem(
            Mimic3Settings(
                voices_directories=[args.voices_dir],
                voices_download_dir=args.voices_dir,
            )
        )

        if "#" in args.voice:
            # Case to handle a multi-speaker voice definition
            voice, _speaker = args.voice.split("#", maxsplit=1)
            _LOGGER.debug("Preloading voice: %s", voice)
            mimic3.preload_voice(voice)
        else:
            _LOGGER.debug("Preloading voice: %s", args.voice)
            mimic3.preload_voice(args.voice)

        _LOGGER.info("Ready")

        mimic3.voice = args.voice

        # Listen for connections
        while True:
            try:
                connection, client_address = sock.accept()
                _LOGGER.debug("Connection from %s", client_address)

                # Start new thread for client
                threading.Thread(
                    target=handle_client,
                    args=(connection, mimic3),
                    daemon=True,
                ).start()
            except KeyboardInterrupt:
                break
            except Exception:
                _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


def handle_client(connection: socket.socket, mimic3: Mimic3TextToSpeechSystem) -> None:
    try:
        with connection, connection.makefile(mode="rwb") as conn_file:
            while True:
                event_info = json.loads(conn_file.readline())
                event_type = event_info["type"]

                if event_type == "synthesize":
                    text = event_info["data"]["text"]
                    _LOGGER.debug("synthesize: text='%s'", text)

                    mimic3.begin_utterance()
                    mimic3.speak_text(text)
                    results = mimic3.end_utterance()

                    is_first_audio = True
                    for result in results:
                        if not isinstance(result, AudioResult):
                            continue

                        data = {
                            "rate": result.sample_rate_hz,
                            "width": result.sample_width_bytes,
                            "channels": result.num_channels,
                        }

                        if is_first_audio:
                            is_first_audio = False
                            conn_file.write(
                                (
                                    json.dumps({"type": "audio-start", "data": data})
                                    + "\n"
                                ).encode()
                            )

                        conn_file.write(
                            (
                                json.dumps(
                                    {
                                        "type": "audio-chunk",
                                        "data": data,
                                        "payload_length": len(result.audio_bytes),
                                    }
                                )
                                + "\n"
                            ).encode()
                        )
                        conn_file.write(result.audio_bytes)

                    conn_file.write(
                        (
                            json.dumps({"type": "audio-stop"}, ensure_ascii=False)
                            + "\n"
                        ).encode()
                    )
                    break
    except Exception:
        _LOGGER.exception("Unexpected error in client thread")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
