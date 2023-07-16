import asyncio
import io
from dataclasses import dataclass

from wyoming.event import (
    Event,
    Eventable,
    async_read_event,
    async_write_event,
    read_event,
    write_event,
)

_NEWLINE = "\n".encode()[0]


@dataclass
class MyEvent(Eventable):

    data_value: str

    payload_value: bytes

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == "MyEvent"

    def event(self) -> Event:
        return Event(
            type="MyEvent",
            data={"data_value": self.data_value},
            payload=self.payload_value,
        )

    @staticmethod
    def from_event(event: Event) -> "MyEvent":
        assert event.data is not None
        assert event.payload is not None

        return MyEvent(
            data_value=event.data["data_value"],
            payload_value=event.payload,
        )


def test_write_read():
    test_event = MyEvent(
        data_value="test data value", payload_value=b"test payload value"
    )

    with io.BytesIO() as event_io:
        write_event(test_event.event(), event_io)
        event_io.seek(0)
        actual_event = read_event(event_io)
        assert MyEvent.is_type(actual_event.type)
        assert MyEvent.from_event(actual_event) == test_event


class FakeReaderWriter:
    def __init__(self):
        self._bytes = bytes()

    async def readline(self) -> bytes:
        for i, b in enumerate(self._bytes):
            if b == _NEWLINE:
                return await self.readexactly(i + 1)

        raise RuntimeError("No newline found")

    async def readexactly(self, n: int) -> bytes:
        assert n <= len(self._bytes)
        data = self._bytes[:n]
        self._bytes = self._bytes[n:]
        return data

    def write(self, data: bytes):
        self._bytes += data

    def writelines(self, lines):
        for data in lines:
            self.write(data)

    async def drain(self):
        pass


def test_async_write_read():
    asyncio.run(_test_async_write_read())


async def _test_async_write_read():
    test_event = MyEvent(
        data_value="test data value", payload_value=b"test payload value"
    )

    reader_writer = FakeReaderWriter()
    await async_write_event(test_event.event(), reader_writer)
    actual_event = await async_read_event(reader_writer)
    assert MyEvent.is_type(actual_event.type)
    assert MyEvent.from_event(actual_event) == test_event
