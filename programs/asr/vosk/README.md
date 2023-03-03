# Vosk

Speech to text service for Rhasspy based on [Vosk](https://alphacephei.com/vosk/).

You can download additional models here: https://alphacephei.com/vosk/models


## Installation

1. Copy the contents of this directory to `config/programs/asr/vosk/`
2. Run `script/setup`
3. Download a model with `script/download.py`
    * Example: `script/download.py en_small`
    * Models are downloaded to `config/data/asr/vosk` directory
4. Test with `script/wav2text`
    * Example `script/wav2text /path/to/vosk-model-small-en-us-0.15/ /path/to/test.wav`
