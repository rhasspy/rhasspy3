# The Wyoming Protocol

An interprocess event protocol over stdin/stdout.


## Event Format

An event is:

1. A single line of JSON with an object:
    * `type` - string (required)
    * `data` - object (optional)
    * `payload_bytes` - number (optional)
2. An optional binary payload of `payload_length` bytes


## Rhasspy Events

| Domain | Type           | Data                            | Payload |
|--------|----------------|---------------------------------|---------|
| audio  | audio-start    | timestamp,rate, width, channels |         |
| audio  | audio-chunk    | timestamp,rate, width, channels | PCM     |
| audio  | audio-stop     | timestamp                       |         |
| wake   | detection      | name                            |         |
| vad    | voice-started  | timestamp                       |         |
| vad    | voice-stopped  | timestamp                       |         |
| asr    | transcription  | text                            |         |
| intent | recognize      | text                            |         |
| intent | intent         | name, entities                  |         |
| intent | not-recognized | text                            |         |
| handle | handled        | text                            |         |
| handle | not-handled    | text                            |         |
| tts    | synthesize     | text                            |         |
| snd    | played         |                                 |         |
