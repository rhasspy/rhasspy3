# Coqui STT

Speech to text service for Rhasspy based on [Coqui STT](https://stt.readthedocs.io/en/latest/).

Additional models can be downloaded here: https://coqui.ai/models/


## Installation

1. Copy the contents of this directory to `config/programs/asr/coqui-stt/`
2. Run `script/setup`
3. Download a model with `script/download.py`
    * Example: `script/download.py en_large`
    * Models are downloaded to `config/data/asr/coqui-stt` directory
4. Test with `script/wav2text`
    * Example `script/wav2text /path/to/english_v1.0.0-large-vocab/ /path/to/test.wav`
