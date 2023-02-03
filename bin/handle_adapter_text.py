#!/usr/bin/env python3
import argparse
import logging
import shlex
import subprocess
from pathlib import Path

from rhasspy3.asr import Transcript
from rhasspy3.event import read_event, write_event
from rhasspy3.handle import Handled, NotHandled

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=args.shell,
        universal_newlines=True,
    )
    with proc:
        assert proc.stdin is not None
        assert proc.stdout is not None

        while True:
            event = read_event()
            if event is None:
                break

            if Transcript.is_type(event.type):
                transcript = Transcript.from_event(event)
                stdout, _stderr = proc.communicate(input=transcript.text)
                handled = False
                for line in stdout.splitlines():
                    line = line.strip()
                    if line:
                        write_event(Handled(text=line).event())
                        handled = True
                        break

                if not handled:
                    write_event(NotHandled().event())

                break


if __name__ == "__main__":
    main()
