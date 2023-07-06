#!/usr/bin/env python3
import argparse
import logging
import socket
import threading
import sys

from rhasspy3.audio import AudioStop
from rhasspy3.event import read_event, write_event

_LOGGER = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("address", help="ip:port of server")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    address, port_str = args.address.split(":", maxsplit=1)
    port = int(port_str)

    _LOGGER.debug("Connecting to %s", args.address)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((address, port))
    _LOGGER.info("Connected")

    try:
        with sock.makefile(mode="rwb") as conn_file:
            read_thread = threading.Thread(
                target=read_proc, args=(conn_file,), daemon=True
            )
            read_thread.start()

            while True:
                event = read_event()
                if event is None:
                    break

                write_event(event, conn_file)

                if AudioStop.is_type(event.type):
                    break
    except KeyboardInterrupt:
        pass


def read_proc(conn_file):
    try:
        while True:
            event = read_event(conn_file)
            if event is None:
                break

            write_event(event)
    except Exception:
        _LOGGER.exception("Unexpected error in read thread")


if __name__ == "__main__":
    main()
