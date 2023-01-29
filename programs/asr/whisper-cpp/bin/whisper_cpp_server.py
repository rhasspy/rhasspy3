#!/usr/bin/env python3
import argparse
import json
import logging
import os
import socket
import threading

import numpy as np
from whisper_cpp import Whisper

_LOGGER = logging.getLogger("whisper_cpp_server")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to whisper.cpp model file")
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

        _LOGGER.debug("Loading model: %s", args.model)
        with Whisper(args.model) as whisper:
            _LOGGER.info("Ready")

            # Listen for connections
            while True:
                try:
                    connection, client_address = sock.accept()
                    _LOGGER.debug("Connection from %s", client_address)

                    # Start new thread for client
                    threading.Thread(
                        target=handle_client,
                        args=(connection, whisper),
                        daemon=True,
                    ).start()
                except KeyboardInterrupt:
                    break
                except Exception:
                    _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


def handle_client(connection: socket.socket, whisper: Whisper) -> None:
    try:
        is_first_audio = True

        with connection, connection.makefile(mode="rwb") as conn_file:
            audio_bytes = bytes()
            while True:
                event_info = json.loads(conn_file.readline())
                event_type = event_info["type"]

                if event_type == "audio-chunk":
                    if is_first_audio:
                        _LOGGER.debug("Receiving audio")
                        is_first_audio = False

                    num_bytes = event_info["payload_length"]
                    audio_bytes += conn_file.read(num_bytes)
                elif event_type == "audio-stop":
                    _LOGGER.debug("Audio stopped")
                    break

            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_array = audio_array.astype(np.float32) / 32768.0
            text = " ".join(whisper.transcribe(audio_array))
            _LOGGER.debug(text)

            transcript_str = (
                json.dumps({"type": "transcript", "data": {"text": text}}) + "\n"
            )
            conn_file.write(transcript_str.encode())
    except Exception:
        _LOGGER.exception("Unexpected error in client thread")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
