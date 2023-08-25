#!/usr/bin/env python3
import argparse
import json
import logging
import os
import socket
import subprocess
import tempfile
import wave
from pathlib import Path

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to model file (.onnx)")
    parser.add_argument(
        "--socketfile", required=True, help="Path to Unix domain socket file"
    )
    parser.add_argument(
        "--auto-punctuation", default=".?!", help="Automatically add punctuation"
    )
    parser.add_argument("--config", help="Path to model config file (default: model path + .json)")
    parser.add_argument("--speaker", type=int, help="ID of speaker (default: 0)")
    parser.add_argument("--noise_scale", type=float, help="Generator noise (default: 0.667)")
    parser.add_argument("--length_scale", type=float, help="Phoneme length (default: 1.0)")
    parser.add_argument("--noise_w", type=float, help="Phoneme width noise (default: 0.8)")
    parser.add_argument("--sentence_silence", type=float, help="Seconds of silence after each sentence (default: 0.2)")
    parser.add_argument("--tashkeel_model", help="Path to libtashkeel onnx model (arabic)")
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

        with tempfile.TemporaryDirectory() as temp_dir:
            command = [
                str(_DIR / "piper"),
                "--model",
                str(args.model),
                "--output_dir",
                temp_dir,
            ]
            if args.config is not None:
                command.append(["--config", args.config])
            if args.speaker is not None:
                command.append(["--speaker", args.speaker])
            if args.noise_scale is not None:
                command.append(["--noise_scale", args.noise_scale])
            if args.length_scale is not None:
                command.append(["--length_scale", args.length_scale])
            if args.noise_w is not None:
                command.append(["--noise_w", args.noise_w])
            if args.sentence_silence is not None:
                command.append(["--sentence_silence", args.sentence_silence])
            if args.tashkeel_model is not None:
                command.append(["--tashkeel_model", args.tashkeel_model])

            with subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=True,
            ) as proc:
                _LOGGER.info("Ready")

                # Listen for connections
                while True:
                    try:
                        connection, client_address = sock.accept()
                        _LOGGER.debug("Connection from %s", client_address)
                        handle_connection(connection, proc, args)
                    except KeyboardInterrupt:
                        break
                    except Exception:
                        _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


def handle_connection(
    connection: socket.socket, proc: subprocess.Popen, args: argparse.Namespace
) -> None:
    assert proc.stdin is not None
    assert proc.stdout is not None

    with connection, connection.makefile(mode="rwb") as conn_file:
        while True:
            event_info = json.loads(conn_file.readline())
            event_type = event_info["type"]

            if event_type != "synthesize":
                continue

            raw_text = event_info["data"]["text"]
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
                data = {
                    "rate": wav_file.getframerate(),
                    "width": wav_file.getsampwidth(),
                    "channels": wav_file.getnchannels(),
                }

                conn_file.write(
                    (
                        json.dumps(
                            {"type": "audio-start", "data": data}, ensure_ascii=False
                        )
                        + "\n"
                    ).encode()
                )

                # Audio
                audio_bytes = wav_file.readframes(wav_file.getnframes())
                conn_file.write(
                    (
                        json.dumps(
                            {
                                "type": "audio-chunk",
                                "data": data,
                                "payload_length": len(audio_bytes),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    ).encode()
                )
                conn_file.write(audio_bytes)

            conn_file.write(
                (json.dumps({"type": "audio-stop"}, ensure_ascii=False) + "\n").encode()
            )
            os.unlink(output_path)
            break


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
