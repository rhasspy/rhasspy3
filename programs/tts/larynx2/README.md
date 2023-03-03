# Larynx 2

Text to speech service for Rhasspy based on [Larynx 2](https://github.com/rhasspy/larynx2).


## Installation

1. Copy the contents of this directory to `config/programs/tts/larynx2/`
2. Run `script/setup`
3. Download a model with `script/download.py`
    * Example: `script/download.py english`
    * Models are downloaded to `config/data/tts/larynx2` directory
4. Test with `bin/larynx`
    * Example `echo 'Welcome to the world of speech synthesis.' | bin/larynx --model /path/to/en-us-blizzard_lessac-medium.onnx --output_file welcome.wav`
