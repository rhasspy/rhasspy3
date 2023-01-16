#!/usr/bin/env python3
import argparse
import logging
import os
import socket
import sys
import threading
from pathlib import Path

import pocketsphinx

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.asr import Transcript
from rhasspy3.event import read_event, write_event

_LOGGER = logging.getLogger("pocketsphinx_server")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Pocketsphinx model directory")
    parser.add_argument(
        "--socketfile", required=True, help="Path to Unix domain socket file"
    )
    parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=16000,
        help="Input audio sample rate (default: 16000)",
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

        model_dir = Path(args.model)

        decoder_config = pocketsphinx.Decoder.default_config()
        decoder_config.set_string("-hmm", str(model_dir / "acoustic_model"))
        decoder_config.set_string("-dict", str(model_dir / "dictionary.txt"))
        decoder_config.set_string("-lm", str(model_dir / "language_model.txt"))
        decoder = pocketsphinx.Decoder(decoder_config)

        # Listen for connections
        while True:
            try:
                connection, client_address = sock.accept()
                _LOGGER.debug("Connection from %s", client_address)

                # Start new thread for client
                threading.Thread(
                    target=handle_client,
                    args=(connection, decoder, args.rate),
                    daemon=True,
                ).start()
            except KeyboardInterrupt:
                break
            except Exception:
                _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


def handle_client(connection: socket.socket, decoder: pocketsphinx.Decoder, rate: int) -> None:
    try:
        decoder.start_utt()
        is_first_audio = True

        with connection, connection.makefile(mode="rwb") as conn_file:
            while True:
                event = read_event(conn_file)
                if event is None:
                    break

                if AudioChunk.is_type(event.type):
                    if is_first_audio:
                        _LOGGER.debug("Receiving audio")
                        is_first_audio = False

                    chunk = AudioChunk.from_event(event)
                    decoder.process_raw(chunk.audio, False, False)
                elif AudioStop.is_type(event.type):
                    _LOGGER.info("Audio stopped")

                    decoder.end_utt()
                    hyp = decoder.hyp()
                    if hyp:
                        text = hyp.hypstr.strip()
                    else:
                        text = ""

                    write_event(Transcript(text=text).event(), conn_file)
                    break
    except Exception:
        _LOGGER.exception("Unexpected error in client thread")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
