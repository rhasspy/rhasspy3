# Tutorial

Welcome to Rhasspy 3! This is a developer preview, so many of the manual steps here will be replaced with something more user-friendly in the future.


## Installing Rhasspy 3

To get started, just clone the repo. Rhasspy's core does not currently have any dependencies outside the Python standard library.

```sh
git clone https://github.com/rhasspy/rhasspy3
cd rhasspy3
```


## Layout

Installed programs and downloaded models are stored in the `config` directory, which is empty by default:

* `rhasspy3/config/`
    * `configuration.yaml` - overrides `rhasspy3/configuration.yaml`
    * `programs/` - installed programs
        * `<domain>/`
            * `<name>/`
    * `data/` - downloaded models
        * `<domain>/`
            * `<name>/`
            
Programs in Rhasspy are divided into [domains](domains.md).


## Configuration

Rhasspy loads two configuration files:

1. `rhasspy3/configuration.yaml` (base)
2. `config/configuration.yaml` (user)

The file in `config` will override the base configuration. You can see what the final configuration looks like with:

```sh
script/run bin/config_print.py
```


## Microphone

Programs that were not designed for Rhasspy can be used with [adapters](adapters.md).
For example, add the following to your `configuration.yaml` (in the `config` directory):

```yaml
programs:
  mic:
    arecord:
      command: |
        arecord -q -r 16000 -c 1 -f S16_LE -t raw -
      adapter: |
        mic_adapter_raw.py --rate 16000 --width 2 --channels 1

pipelines:
  default:
    mic:
      name: arecord
```

Now you can run a microphone test:

```sh
script/run bin/mic_test_energy.py
```

When speaking, you should see the bar change with volume. If not, check the available devices with `arecord -L` and update the `arecord` command in `configuration.yaml` with `-D <device_name>` (prefer devices that start with `plughw:`).

Press CTRL+C to quit.

Pipelines will be discussed later. For now, know that the pipeline named `default` will be run if you don't specify one. The mic test script can do this:

```sh
script/run bin/mic_test_energy.py --pipeline my-pipeline
```

You can also override the mic program:

```sh
script/run bin/mic_test_energy.py --mic-program other-program-from-config
```


## Voice Activity Detection

Let's install our first program, [Silero VAD](https://github.com/snakers4/silero-vad/).
Start by copying from `programs/` to `config/programs`, then run the setup script:

```sh
mkdir -p config/programs/vad/
cp -R programs/vad/silero config/programs/vad/
config/programs/vad/silero/script/setup
```

Once the setup script completes, add the following to your `configuration.yaml`:

```yaml
programs:
  mic: ...
  vad:
    silero:
      command: |
        script/speech_prob "share/silero_vad.onnx"
      adapter: |
        vad_adapter_raw.py --rate 16000 --width 2 --channels 1 --samples-per-chunk 512

pipelines:
  default:
    mic: ...
    vad:
      name: silero
```


This calls a command inside `config/programs/vad/silero` and uses an adapter. Notice that the command's working directory will always be `config/programs/<domain>/<name>`.

You can test out the voice activity detection (VAD) by recording an audio sample:

```sh
script/run bin/mic_record_sample.py sample.wav
```

Say something for a few seconds and then wait for the program to finish. Afterwards, listen to `sample.wav` and verify that it sounds correct. You may need to adjust microphone settings with `alsamixer`


## Speech to Text

Now for the fun part! We'll be installing [faster-whisper](https://github.com/guillaumekln/faster-whisper/), an optimized version of Open AI's [Whisper](https://github.com/openai/whisper) model.


```sh
mkdir -p config/programs/asr/
cp -R programs/asr/faster-whisper config/programs/asr/
config/programs/asr/faster-whisper/script/setup
```

Before using faster-whisper, we need to download a model:

```sh
config/programs/asr/faster-whisper/script/download.py tiny-int8
```

Notice that the model was downloaded to `config/data/asr/faster-whisper`:

```sh
tree config/data/asr/faster-whisper/
config/data/asr/faster-whisper/
└── tiny-int8
    ├── config.json
    ├── model.bin
    └── vocabulary.txt
```

The `tiny-int8` model is the smallest and fastest model, but may not give the best transcriptions. Run `download.py` without any arguments to see the available models, or follow [the instructions](https://github.com/guillaumekln/faster-whisper/#model-conversion) to make your own!

Add the following to `configuration.yaml`:

```yaml
programs:
  mic: ...
  vad: ...
  asr:
    faster-whisper:
      command: |
        script/wav2text "${data_dir}/tiny-int8" "{wav_file}"
      adapter: |
        asr_adapter_wav2text.py

pipelines:
  default:
    mic: ...
    vad: ...
    asr:
      name: faster-whisper
```

You can now transcribe a voice command:

```sh
script/run bin/asr_transcribe.py
```

(say something)

You should see a transcription of what you said as part of an [event](wyoming.md).

### Client/Server

Speech to text systems can take a while to load their models, so a lot of time is wasted if we start from scratch each time.

Some speech to text and text to speech programs have included servers. These usually use [Unix domain sockets](https://en.wikipedia.org/wiki/Unix_domain_socket) to communicate with a small client program.

Add the following to your `configuration.yaml`:


```yaml
programs:
  mic: ...
  vad: ...
  asr:
    faster-whisper: ...
    faster-whisper.client:
      command: |
        client_unix_socket.py var/run/faster-whisper.socket

servers:
  asr:
    faster-whisper:
      command: |
        script/server --language "en" "${data_dir}/tiny-int8"

pipelines:
  default:
    mic: ...
    vad: ...
    asr:
      name: faster-whisper.client
```

Start the server in a separate terminal:

```sh
script/run bin/server_run.py asr faster-whisper
```

When it prints "Ready", transcribe yourself speaking again:

```sh
script/run bin/asr_transcribe.py
```

(say something)

You should receive your transcription a bit faster than before.


### HTTP Server

Rhasspy includes a small HTTP server that allows you to access programs and pipelines over a web API. To get started, run the setup script:

```sh
script/setup_http_server
```

Run HTTP server in a separate terminal:

```sh
script/http_server --debug
```

Now you can transcribe a WAV file over HTTP:

```sh
curl -X POST -H 'Content-Type: audio/wav' --data-binary @etc/what_time_is_it.wav 'localhost:13331/asr/transcribe'
```

You can run one or more program servers along with the HTTP server:

```sh
script/http_server --debug --server asr faster-whisper
```

**NOTE:** You will need to restart the HTTP server when you change `configuration.yaml`


## Wake Word Detection

Next, we'll install [Porcupine](https://github.com/Picovoice/porcupine):

```sh
mkdir -p config/programs/wake/
cp -R programs/wake/porcupine1 config/programs/wake/
config/programs/wake/porcupine1/script/setup
```

Check available wake word models with:

```sh
config/programs/wake/porcupine1/script/list_models
alexa_linux.ppn
americano_linux.ppn
blueberry_linux.ppn
bumblebee_linux.ppn
computer_linux.ppn
grapefruit_linux.ppn
grasshopper_linux.ppn
hey google_linux.ppn
hey siri_linux.ppn
jarvis_linux.ppn
ok google_linux.ppn
pico clock_linux.ppn
picovoice_linux.ppn
porcupine_linux.ppn
smart mirror_linux.ppn
snowboy_linux.ppn
terminator_linux.ppn
view glass_linux.ppn
```

**NOTE:** These will be slightly different on a Raspberry Pi (`_raspberry-pi.ppn` instead of `_linux.ppn`).

Add to `configuration.yaml`:

```yaml
programs:
  mic: ...
  vad: ...
  asr: ...
  wake:
    porcupine1:
      command: |
        .venv/bin/python3 bin/porcupine_stream.py --model "${model}"
      template_args:
        model: "porcupine_linux.ppn"

servers:
  asr: ...

pipelines:
  default:
    mic: ...
    vad: ...
    asr: ...
    wake:
      name: porcupine1
```

Notice that we include `template_args` in the `programs` section. This lets us change specific settings in `pipelines`, which will be demonstrated in a moment.

Test wake word detection:

```sh
script/run bin/wake_detect.py --debug
```

(say "porcupine")

Now change the model in `configuration.yaml`:

```yaml
programs:
  mic: ...
  vad: ...
  asr: ...
  wake: ...

servers:
  asr: ...

pipelines:
  default:
    mic: ...
    vad: ...
    asr: ...
    wake:
      name: porcupine1
      template_args:
        model: "grasshopper_linux.ppn"
```

Test wake word detection again:

```sh
script/run bin/wake_detect.py --debug
```

(say "grasshopper")

Test over HTTP server (restart server):

```sh
curl -X POST 'localhost:13331/pipeline/run?stop_after=wake'
```

(say "grasshopper")

Test full voice command:

```sh
curl -X POST 'localhost:13331/pipeline/run?stop_after=asr'
```

(say "grasshopper", *pause*, voice command, *wait*)



## Intent Handling

There are two types of intent handlers in Rhasspy, ones that handle transcripts directly (text) and others that handle structured intents (name + entities). For this example, we will be handling text directly from `asr`.

In `configuration.yaml`:

```yaml
programs:
  mic: ...
  vad: ...
  asr: ...
  wake: ...
  handle:
    date_time:
      command: |
        bin/date_time.py
      adapter: |
        handle_adapter_text.py

servers:
  asr: ...

pipelines:
  default:
    mic: ...
    vad: ...
    asr: ...
    wake: ...
    handle:
      name: date_time

```

Install date time demo script:

```sh
mkdir -p config/programs/handle/
cp -R programs/handle/date_time config/programs/handle/
```

This script just looks for the words "date" and "time" in the text, and responds appropriately.

You can test it on some text:

```sh
echo 'What time is it?' | script/run bin/handle_text.py --debug
```

Now let's test it with a full voice command:

```sh
script/run bin/pipeline_run.py --debug --stop-after handle
```

(say "grasshopper", *pause*, "what time is it?")

It works too over HTTP (restart server):

```sh
curl -X POST 'localhost:13331/pipeline/run?stop_after=handle'
```

(say "grasshopper", *pause*, "what's the date?")


## Text to Speech and Sound

The final stages of our pipeline will be text to speech (`tts`) and audio output (`snd`).

Install [Piper](https://github.com/rhasspy/piper):

```sh
mkdir -p config/programs/tts/
cp -R programs/tts/piper config/programs/tts/
config/programs/tts/piper/script/setup.py
```

and download an English voice:

```sh
config/programs/tts/piper/script/download.py english
```

Call `download.py` without any arguments to see available voices.

Add to `configuration.yaml`:

```yaml
programs:
  mic: ...
  vad: ...
  asr: ...
  wake: ...
  handle: ...
  tts:
    piper:
      command: |
        bin/piper --model "${model}" --output_file -
      adapter: |
        tts_adapter_text2wav.py
      template_args:
        model: "${data_dir}/en-us-blizzard_lessac-medium.onnx"
  snd:
    aplay:
      command: |
        aplay -q -r 22050 -f S16_LE -c 1 -t raw
      adapter: |
        snd_adapter_raw.py --rate 22050 --width 2 --channels 1

servers:
  asr: ...

pipelines:
  default:
    mic: ...
    vad: ...
    asr: ...
    wake: ...
    handle: ...
    tts:
      name: piper
    snd:
      name: aplay
```


We can test the text to speech and audio output programs:

```sh
script/run bin/tts_speak.py 'Welcome to the world of speech synthesis.'
```

The `bin/tts_synthesize.py` can be used if you want to just output a WAV file.

```sh
script/run bin/tts_synthesize.py 'Welcome to the world of speech synthesis.' > welcome.wav
```

This also works over HTTP (restart server):

```sh
curl -X POST \
  --data 'Welcome to the world of speech synthesis.' \
  --output welcome.wav \
  'localhost:13331/tts/synthesize'
```

Or to speak over HTTP:

```sh
curl -X POST --data 'Welcome to the world of speech synthesis.' 'localhost:13331/tts/speak'
```


### Client/Server

Like speech to text, text to speech models can take a while to load. Let's add a server for Piper to `configuration.yaml`:

```yaml
programs:
  mic: ...
  vad: ...
  asr: ...
  wake: ...
  handle: ...
  tts:
    piper.client:
      command: |
        client_unix_socket.py var/run/piper.socket
  snd: ...

servers:
  asr: ...
  tts:
    piper:
      command: |
        script/server "${model}"
      template_args:
        model: "${data_dir}/en-us-blizzard_lessac-medium.onnx"

pipelines:
  default:
    mic: ...
    vad: ...
    asr: ...
    wake: ...
    handle: ...
    tts:
      name: piper.client
    snd: ...
```

Now we can run both servers with the HTTP server:

```sh
script/http_server --debug --server asr faster-whisper --server tts piper
```

Text to speech requests should be faster now.


## Complete Pipeline

As a final example, let's run a complete pipeline from wake word detection to text to speech response:

```sh
script/run bin/pipeline_run.py --debug
```

(say "grasshopper", *pause*, "what time is it?", *wait*)

Rhasspy should speak the current time.

This also works over HTTP:

```sh
curl -X POST 'localhost:13331/pipeline/run'
```

(say "grasshopper", *pause*, "what is the date?", *wait*)

Rhasspy should speak the current date.


## Next Steps

* Connect Rhasspy to [Home Assistant](home_assistant.md)
* Run one or more [satellites](satellite.md)
