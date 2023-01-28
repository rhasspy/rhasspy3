# Rhasspy 3

An open source toolkit for building voice assistants.


## Programs

* mic
    * arecord
    * gstreamer_udp
    * udp_raw
* wake 
    * porcupine1
    * precise-lite
    * snowboy
* vad
    * silero
    * energy
* asr 
    * vosk
    * coqui-stt
    * whisper
    * whisper-cpp
    * pocketsphinx
* intent
    * regex
* tts 
    * larynx1
    * larynx2
    * coqui-tts
    * marytts
    * flite
    * festival
    * espeak-ng
* snd
    * aplay
    
    
## Services

* asr
    * vosk
    * coqui-stt
    * whisper
    * whisper-cpp
    * pocketsphinx
* tts
    * larynx1
    * larynx2
    * coqui-tts


## Pipelines

1. mic - audio is recorded from a microphone or satellite
2. wake - wake word (or hotword) is detected in audio
3. vad - start/end of voice command are detected in audio
4. asr - audio is transcribed into text
5. intent - user's intent is recognized from text
6. handle - intent is handled and a text response is produced
7. tts - text is synthesized into audio
8. snd - synthesized audio is played through speakers or satellite


## HTTP API

`http://localhost:12101/<endpoint>`

* `/api/run-pipeline`
    * Runs a full pipeline from mic to snd
    * Can accept WAV audio input
    * Produces pipeline result JSON or tts WAV audio (skip snd)
* `/api/listen-for-command`
    * Runs a pipeline until intent is handled
    * Can accept WAV audio input
    * Produces intent JSON
* `/api/wait-for-wake`
    * Runs a pipeline until wake word is detected
    * Can accept WAV audio input
    * Produces detection JSON
* `/api/speech-to-text`
    * Runs a pipeline until speech is transcribed
    * Can accept WAV audio input
    * Produces transcription JSON
* `/api/speech-to-intent`
    * Runs a pipeline until intent is recognized
    * Can accept WAV audio input
    * Produces intent JSON
* `/api/text-to-intent`
    * Runs a pipeline until intent is recognized, skipping audio input
    * Produces intent JSON
* `/api/text-to-speech`
    * Synthesizes audio from text
    * Produces WAV output or plays via snd
* `/api/play-wav`
    * Plays WAV audio via snd
* `/api/version`
    * Returns version info

## WebSocket API

`ws://localhost:12101/<endpoint>`

* `/api/stream-pipeline`
    * Runs a full pipeline from mic to snd
    * Audio from websocket as raw chunks
    * Produces pipeline result JSON or tts audio (skip snd)
* `/api/stream-command`
    * Runs a pipeline until intent is handled
    * Audio from websocket as raw chunks
    * Produces intent JSON
* `/api/stream-to-wake`
    * Runs a pipeline until wake word is detected
    * Audio from websocket as raw chunks
    * Produces detection JSON
* `/api/stream-to-text`
    * Runs a pipeline until speech is transcribed
    * Audio from websocket as raw chunks
    * Produces transcription JSON
* `/api/stream-to-intent`
    * Runs a pipeline until intent is recognized
    * Audio from websocket as raw chunks
    * Produces intent JSON
* `/api/play-stream`
    * Plays raw audio via snd
    * Audio from websocket as raw chunks
