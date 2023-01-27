# Rhasspy 3


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
* asr 
    * vosk
    * coqui-stt
    * whisper
    * whisper-cpp
    * pocketsphinx
* intent
    * regex
* tts 
    * larynx2
    * coqui-tts
    * marytts
    * flite
    * festival
    * espeak-ng
* snd
    * aplay


## Pipelines


## HTTP API

`http://localhost:12101/<endpoint>`

* `/api/listen-for-command`
* `/api/wait-for-wake`
* `/api/speech-to-text`
* `/api/speech-to-intent`
* `/api/text-to-intent`
* `/api/text-to-speech`
* `/api/play-wav`
* `/api/version`
