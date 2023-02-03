# Rhasspy 3

**NOTE: This is a very early alpha release!**

An open source toolkit for building voice assistants.

Rhasspy focuses on:

* Privacy - no data leaves your computer
* Broad language support - more than just English
* Customization - everything can be changed


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
    * energy (TODO)
* asr 
    * vosk
    * coqui-stt
    * whisper
    * whisper-cpp
    * pocketsphinx
* intent
    * regex
* tts 
    * larynx1 (TODO)
    * larynx2
    * mimic3
    * coqui-tts
    * marytts
    * flite
    * festival
    * espeak-ng
* snd
    * aplay
    
    
## Servers

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
    * mimic3


## Pipelines

1. mic - audio is recorded from a microphone or satellite
2. wake - wake word (or hotword) is detected in audio
3. vad - start/end of voice command are detected in audio
4. asr - audio is transcribed into text
5. intent - user's intent is recognized from text
6. handle - intent is handled and a text response is produced
7. tts - text is synthesized into audio
8. snd - synthesized audio is played through speakers or satellite


## Adapters

In `bin/`:

* `asr_adapter_raw2text.py`
* `asr_adapter_wav2text.py`
* `handle_adapter_json.py`
* `handle_adapter_text.py`
* `snd_adapter_raw.py`


## Utilities

In `bin/`:

* `asr_transcribe.py`
* `asr_transcribe_wav.py`
* `asr_transcribe_stream.py`
* `handle_handle.py`
* `intent_recognize.py`
* TODO `mic_record_wav.py`
* `server_run.py`
* `snd_play.py`
* `tts_speak.py`
* `wake_detect.py`

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
