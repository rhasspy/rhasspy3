# Adapters

Scripts in `bin/`:

* `asr_adapter_raw2text.py`
    * Raw audio stream in, text or JSON out
* `asr_adapter_wav2text.py`
    * WAV file(s) in, text or JSON out (per file)
* `handle_adapter_json.py`
    * Intent JSON in, text response out
* `handle_adapter_text.py`
    * Transcription in, text response out
* `mic_adapter_raw.py`
    * Raw audio stream in
* `snd_adapter_raw.py`
    * Raw audio stream out
* `tts_adapter_http.py`
    * HTTP POST to endpoint with text, WAV out
* `tts_adapter_text2wav.py`
    * Text in, WAV out
* `vad_adapter_raw.py`
    * Raw audio stream in, speech probability out (one line per chunk)
* `wake_adapter_raw.py`
    * Raw audio stream in, name of detected model out (one line per detection)
* `client_unix_socket.py`
    * Send/receive events over Unix domain socket


![Wyoming protocol adapter](img/adapter.png)
