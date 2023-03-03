# Faster Whisper

Speech to text service for Rhasspy based on [faster-whisper](https://github.com/guillaumekln/faster-whisper/).

Additional models can be downloaded here: https://github.com/rhasspy/models/releases/tag/v1.0

## Installation

1. Copy the contents of this directory to `config/programs/asr/faster-whisper/`
2. Run `script/setup.py`
3. Download a model with `script/download.py`
    * Example: `script/download.py tiny-int8`
    * Models are downloaded to `config/data/asr/faster-whisper` directory
4. Test with `script/wav2text`
    * Example `script/wav2text /path/to/tiny-int8/ /path/to/test.wav`
