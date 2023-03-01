# Satellite

Once you have a Rhasspy HTTP server running, you can use Rhasspy as a satellite on a separate device.

**NOTE:** Rhasspy satellites do not need to run Python or any Rhasspy software. They can use the websocket API directly, or talk directly to a running pipeline.

On your satellite, clone the repo:

```sh
git clone https://github.com/rhasspy/rhasspy3
cd rhasspy3
```

Install the websocket utility:

```sh
mkdir -p config/programs/remote/
cp -R programs/remote/websocket config/programs/remote/
config/programs/remote/websocket/script/setup
```

Install [Porcupine](https://github.com/Picovoice/porcupine):

```sh
mkdir -p config/programs/wake/
cp -R programs/wake/porcupine1 config/programs/wake/
config/programs/wake/porcupine1/script/setup
```

Check available wake word models by running 

```sh
config/programs/wake/porcupine1/script/list_models
```

and choose one. We'll use "porcupine_linux.ppn" as an example, but this will be **different on a Raspberry Pi**.

Next, create `config/configuration.yaml` with:

```yaml
programs:
  mic:
    arecord:
      command: |
        arecord -q -r 16000 -c 1 -f S16_LE -t raw -
      adapter: |
        mic_adapter_raw.py --samples-per-chunk 1024 --rate 16000 --width 2 --channels 1

  wake:
    porcupine1:
      command: |
        .venv/bin/python3 bin/porcupine_stream.py --model "${model}"
      template_args:
        model: "porcupine_linux.ppn"

  remote:
    websocket:
      command: |
        script/run "${uri}"
      template_args:
        uri: "ws://localhost:13331/pipeline/asr-tts"

satellites:
  default:
    mic:
      name: arecord
    wake:
      name: porcupine1
    remote:
      name: websocket
    snd:
      name: aplay
```

Replace the model in `porcupine1` with your selection, and adjust the URI in `websocket` to point to your Rhasspy server.

Now you can run your satellite:

```sh
script/run bin/satellite_run.py --debug --loop
```

(say "porcupine", *pause*, say voice command, *wait*)

If everything is working, you should hear a response being spoken. Press CTRL+C to quit.
