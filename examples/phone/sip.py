import argparse
import asyncio
import logging

CRLF = "\r\n"
_LOGGER = logging.getLogger("voip")


class EchoServerProtocol:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            message = data.decode()
            method, headers, body = self._parse_sip(message)

            _LOGGER.debug("Received %s", method)
            _LOGGER.debug(headers)
            _LOGGER.debug(body)

            if method.lower() != "invite":
                return

            _LOGGER.info("Incoming call")

            out_port = self._get_rtp_port(body)
            _LOGGER.debug("RTP output port: %s", out_port)

            self._send_ok(headers, addr)
        except Exception:
            _LOGGER.exception("datagram_received")

    def _parse_sip(self, message: str):
        lines = message.splitlines()

        method = None
        headers = {}
        offset = 0

        for i, line in enumerate(lines):
            if line:
                offset += len(line) + len(CRLF)

            if i == 0:
                method = line.split()[0]
            elif not line:
                break
            else:
                key, value = line.split(":", maxsplit=1)
                headers[key.lower()] = value.strip()

        body = message[offset:]

        return method, headers, body

    def _get_rtp_port(self, sip_body: str):
        # Extract RTP port from SIP body
        body_lines = sip_body.splitlines()
        out_port = None
        for line in body_lines:
            line = line.strip()
            if line:
                key, value = line.split("=", maxsplit=1)
                if key == "m":
                    parts = value.split()
                    if parts[0] == "audio":
                        out_port = int(parts[1])

        return out_port

    def _send_ringing(self, headers, addr):
        response_headers = {
            "Via": headers["via"],
            "From": headers["from"],
            "To": headers["to"],
            "Call-ID": headers["call-id"],
            "Content-Length": 0,
            "CSeq": headers["cseq"],
            "Contact": headers["contact"],
            "User-Agent": "test 1.0",
            "Allow": "INVITE, ACK, BYE, CANCEL, OPTIONS",
        }

        response_lines = ["SIP/2.0 180 Ringing"]
        for key, value in response_headers.items():
            response_lines.append(f"{key}: {value}")

        response_lines.append(CRLF)
        response_str = CRLF.join(response_lines)
        response_bytes = response_str.encode()

        self.transport.sendto(response_bytes, addr)
        _LOGGER.debug("Sent Ringing")

    def _send_ok(self, headers, addr):
        body_lines = [
            "v=0",
            f"o=test 1234 1 IN IP4 {self.args.sip_ip}",
            "s=test 1.0",
            f"c=IN IP4 {self.args.sip_ip}",
            "t=0 0",
            f"m=audio {self.args.rtp_port} RTP/AVP 123",
            "a=rtpmap:123 opus/48000/2",
            "a=ptime:20",
            "a=maxptime:150",
            "a=sendrecv",
            CRLF,
        ]
        body = CRLF.join(body_lines)

        response_headers = {
            "Via": headers["via"],
            "From": headers["from"],
            "To": headers["to"],
            "Call-ID": headers["call-id"],
            "Content-Type": "application/sdp",
            "Content-Length": len(body),
            "CSeq": headers["cseq"],
            "Contact": headers["contact"],
            "User-Agent": "test 1.0",
            "Allow": "INVITE, ACK, BYE, CANCEL, OPTIONS",
        }
        response_lines = ["SIP/2.0 200 OK"]

        for key, value in response_headers.items():
            response_lines.append(f"{key}: {value}")

        response_lines.append(CRLF)
        response_str = CRLF.join(response_lines) + body
        response_bytes = response_str.encode()

        self.transport.sendto(response_bytes, addr)
        _LOGGER.debug("Sent OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sip_ip", help="IP address to advertise to SIP")
    parser.add_argument("--bind-ip", default="0.0.0.0", help="IP address to bind to")
    parser.add_argument("--rtp-port", type=int, default=5004, help="Port for RTP audio")
    parser.add_argument("--sip-port", type=int, default=5060, help="Port for SIP")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    _LOGGER.debug(args)

    loop = asyncio.get_event_loop()

    # One protocol instance will be created to serve all
    # client requests.
    loop.run_until_complete(
        loop.create_datagram_endpoint(
            lambda: EchoServerProtocol(args),
            local_addr=(args.bind_ip, args.sip_port),
        )
    )

    _LOGGER.info("Ready")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
