#!/usr/bin/env python3
import argparse
import io
import logging
import os
import selectors
import socket
import subprocess
import sys
import wave
from pathlib import Path
from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.tts import Synthesize

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def get_voice_config(model) -> dict:
    """Generate sample wav to get samplerate, samplewidth, and channels of the voice."""
    command = [
        str(_DIR / "piper"),
        "--model",
        str(model),
        "--output_file",
        "-",
    ]
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    try:
        wav_str, _ = proc.communicate(b"\n", timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        wav_str, _ = proc.communicate()

    with io.BytesIO(wav_str) as wav_io:
        wav_file: wave.Wave_write = wave.open(wav_io, "rb")
        with wav_file:
            rate = wav_file.getframerate()
            width = wav_file.getsampwidth()
            channels = wav_file.getnchannels()
    return {"rate": rate, "width": width, "channels": channels}


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

    voice_config = get_voice_config(args.model)
    _LOGGER.debug("voice_config: %s", voice_config)

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

        command = [
            str(_DIR / "piper"),
            "--model",
            str(args.model),
            "--output_raw",
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
            stderr=subprocess.PIPE,
        ) as proc:
            _LOGGER.info("Ready")

            # Listen for connections
            while True:
                try:
                    connection, client_address = sock.accept()
                    _LOGGER.debug("Connection from %s", client_address)
                    handle_connection(connection, proc, args, voice_config)
                except KeyboardInterrupt:
                    break
                except Exception:
                    _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


def handle_connection(
    connection: socket.socket,
    proc: subprocess.Popen,
    args: argparse.Namespace,
    voice_config: dict,
) -> None:
    assert proc.stdin is not None
    assert proc.stdout is not None

    with connection, connection.makefile(mode="rwb") as conn_file:
        while True:
            event = read_event(conn_file)  # type: ignore
            if event is None:
                continue

            if not Synthesize.is_type(event.type):
                continue

            raw_text = Synthesize.from_event(event).text
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
            proc.stdin.write(bytes(text.strip() + "\n", "utf8"))
            proc.stdin.flush()

            sel = selectors.DefaultSelector()
            sel.register(proc.stdout, selectors.EVENT_READ)
            sel.register(proc.stderr, selectors.EVENT_READ)

            audio_started = False
            audio_stopped = False
            while True:
                # Wait for stdout or stderr output from the process (blocking).
                # If we already got a message on stderr that the synthesizing has finished,
                # then just poll (non-blocking) until stdout is empty. We will know that
                # when the non-blocking select(timeout=0) returns an empty set
                rlist = sel.select(timeout=0 if audio_stopped else None)
                if not rlist:
                    break
                for key, _ in rlist:
                    output = key.fileobj.read1()
                    if not output:
                        break
                    if key.fileobj is proc.stderr:
                        sys.stderr.buffer.write(output)
                        if "Real-time factor" in output.decode():
                            audio_stopped = True
                        continue

                    if not audio_started:
                        write_event(AudioStart(
                            rate=voice_config["rate"],
                            width=voice_config["width"],
                            channels=voice_config["channels"],
                        ).event(), conn_file)  # type: ignore
                        audio_started = True
                    # Audio
                    write_event(AudioChunk(
                        rate=voice_config["rate"],
                        width=voice_config["width"],
                        channels=voice_config["channels"],
                        audio=output,
                    ).event(), conn_file)  # type: ignore

            write_event(AudioStop().event(), conn_file)  # type: ignore
            break


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
