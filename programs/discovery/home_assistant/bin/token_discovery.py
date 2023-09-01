#!/usr/bin/env python3
import argparse
import asyncio
import logging
import socket
import json
from functools import partial
from pathlib import Path

from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

MDNS_TARGET_IP = "224.0.0.251"

_LOGGER = logging.getLogger()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--token-path", required=True, help="Home Assistant authorization token"
    )
    parser.add_argument(
        "--discovery-port",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--discovery-host",
    )
    #
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print DEBUG messages to console",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    token_path = Path(args.token_path)
    if token_path.exists():
        # Load existing token
        _LOGGER.debug("Token exists: %s", token_path)
        return

    token_path.parent.mkdir(parents=True, exist_ok=True)

    # Detect IP
    if not args.discovery_host:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.setblocking(False)
        test_sock.connect((MDNS_TARGET_IP, 1))
        args.discovery_host = test_sock.getsockname()[0]
        _LOGGER.debug("Detected IP: %s", args.discovery_host)

    if args.discovery_port <= 0:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.bind((args.discovery_host, 0))
        args.discovery_port = test_sock.getsockname()[1]

    discovery_server = await asyncio.start_server(
        partial(handle_discovery, token_path=token_path),
        args.discovery_host,
        args.discovery_port,
    )

    service_info = AsyncServiceInfo(
        "_rhasspy._tcp.local.",
        "HA Satellite._rhasspy._tcp.local.",
        addresses=[socket.inet_aton(args.discovery_host)],
        port=args.discovery_port,
    )
    aiozc = AsyncZeroconf()
    await aiozc.async_register_service(service_info)

    async with discovery_server:
        _LOGGER.info(
            "Waiting for token via discovery (host=%s, port=%s)",
            args.discovery_host,
            args.discovery_port,
        )
        await discovery_server.serve_forever()


async def handle_discovery(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    token_path: Path,
):
    try:
        data = json.loads(await reader.readline())
        _LOGGER.debug("Received token")
        token_path.write_text(data["token"], encoding="utf-8")
        _LOGGER.info("Wrote token to %s", token_path)

        writer.write((json.dumps({"result": "ok"}) + "\n").encode("utf-8"))
        await writer.drain()

        # Close connection
        writer.close()
        await writer.wait_closed()
    except Exception:
        _LOGGER.exception("Unexpected error in handle_discovery")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
