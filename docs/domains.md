# Domains

Programs belong to a specific domain. This defines the kinds of [events](wyoming.md) they are expected to receive and emit.

## mic

Emits `audio-chunk` events, ideally with a `timestamp`.


## wake

Receives `audio-chunk` events.
Emits `detection` event(s) or a `not-detected` event if the program exits without a detection.


## asr

Receives an `audio-start` event, followed by zero or more `audio-chunk` events.

An `audio-stop` event must trigger a `transcript` event to be emitted.


## vad

Receives `audio-chunk` events.

Emits `voice-started` with the `timestamp` of the `audio-chunk` when the user started speaking.

Emits `voice-stopped` with the `timestamp` of the `audio-chunk` when the user finished speaking.


## intent

Optional. The `handle` domain can handle `transcript` events directly.

Receives `recognize` events.

Emits either an `intent` or a `not-recognized` event.


## handle

Receives one of the following event types: `transcript`, `intent`, or `not-recognized`.

Emits either a `handle` or `not-handled` event.


## tts

Receives a `synthesize` event.

Emits an `audio-start` event followed by zero or more `audio-chunk` events, and then an `audio-stop` event.


## snd

Receives `audio-chunk` events until an `audio-stop` event.

Must emit `played` event when audio has finished playing.
