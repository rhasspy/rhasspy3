# Whisper + Home Assistant

```yaml
programs:
  mic:
    arecord:
      command: |
        arecord -q -r 16000 -c 1 -f S16_LE -t raw -
      adapter: |
        mic_adapter_raw.py --rate 16000 --width 2 --channels 1
  vad:
    silero:
      command: |
        .venv/bin/python3 bin/silero_stream.py share/silero_vad.onnx
  asr:
    whisper-cpp.client:
      command: |
        client_unix_socket.py var/run/whisper-cpp.socket

  wake:
    porcupine1:
      command: |
        .venv/bin/python3 bin/porcupine_raw_text.py --model porcupine_linux.ppn
      adapter: |
        wake_adapter_raw.py

  tts:
    larynx2.client:
      command: |
        client_unix_socket.py var/run/larynx2.socket
  snd:
    aplay:
      command: |
        aplay -q -r 22050 -f S16_LE -c 1 -t raw
      adapter: |
        snd_adapter_raw.py --rate 22050 --width 2 --channels 1

  handle:
    date_time:
      command: |
        bin/date_time.py
      adapter: |
        handle_adapter_text.py
    home_assistant_conversation:
      command: |
        bin/converse.py ${url} ${token_file}
      template_args:
        url: "http://localhost:8123/api/conversation/process"
        token_file: "etc/token"
      adapter: |
        handle_adapter_text.py

servers:
  asr:
    whisper-cpp:
      command: |
        script/server ${model}
      template_args:
        model: "share/ggml-base.en.bin"
  tts:
    larynx2:
      command: |
        script/server ${model}
      template_args:
        model: "share/en-us-blizzard_lessac-medium.onnx"

pipelines:
  default:
    mic:
      name: arecord
    vad:
      name: silero
    asr:
      name: whisper-cpp.client
    wake:
      name: porcupine1
    handle:
      name: home_assistant_conversation
    tts:
      name: larynx2.client
    snd:
      name: aplay
```

