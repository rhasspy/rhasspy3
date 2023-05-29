#!/usr/bin/env python3
import argparse
import logging
import socket
import threading
import re

from rhasspy3.event import read_event, write_event

_LOGGER = logging.getLogger("wrapper_unix_socket")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("socketfile", help="Path to Unix domain socket file or host/port combination in the form '1.2.3.4:1234'")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    hostport_match = re.match("^(?P<host>[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}):(?P<port>[0-9]+)$", args.socketfile)
    if hostport_match is not None:
        host = hostport_match["host"]
        port = int(hostport_match["port"])
        _LOGGER.debug("Connecting to %s:%d", host, port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
    else:
        _LOGGER.debug("Connecting to %s", args.socketfile)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(args.socketfile)
    _LOGGER.debug("Connected")

    try:
        with sock.makefile(mode="rwb") as conn_file:
            read_thread = threading.Thread(
                target=read_proc, args=(conn_file,), daemon=True
            )
            read_thread.start()

            write_thread = threading.Thread(
                target=write_proc, args=(conn_file,), daemon=True
            )
            write_thread.start()
            write_thread.join()
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


def write_proc(conn_file):
    try:
        while True:
            event = read_event()
            if event is None:
                break

            write_event(event, conn_file)
    except Exception:
        _LOGGER.exception("Unexpected error in write thread")


if __name__ == "__main__":
    main()
