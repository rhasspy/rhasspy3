# The Wyoming Protocol

An interprocess event protocol over stdin/stdout.

Effectively [JSONL](https://jsonlines.org/) with an optional binary payload.


## Event Format

An event is:

1. A single line of JSON with an object:
    * `type` - string (required)
    * `data` - object (optional)
    * `payload_length` - number (optional)
2. An optional binary payload of exactly `payload_length` bytes

Example:

```json
{ "type": "audio-chunk", data: { "rate": 16000, "width", "channels": 1 }, "payload_length": 2048 }
<2048 bytes>
```


## Rhasspy Events

| Domain | Type           | Data                             | Payload |
|--------|----------------|----------------------------------|---------|
| audio  | audio-start    | timestamp, rate, width, channels |         |
| audio  | audio-chunk    | timestamp, rate, width, channels | PCM     |
| audio  | audio-stop     | timestamp                        |         |
| wake   | detection      | name                             |         |
| wake   | not-detected   |                                  |         |
| vad    | voice-started  | timestamp                        |         |
| vad    | voice-stopped  | timestamp                        |         |
| asr    | transcript     | text                             |         |
| intent | recognize      | text                             |         |
| intent | intent         | name, entities                   |         |
| intent | not-recognized | text                             |         |
| handle | handled        | text                             |         |
| handle | not-handled    | text                             |         |
| tts    | synthesize     | text                             |         |
| snd    | played         |                                  |         |
