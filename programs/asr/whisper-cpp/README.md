# Whisper.cpp

Speech to text service for Rhasspy based on [whisper.cpp](https://github.com/ggerganov/whisper.cpp/).

Additional models can be downloaded here: https://huggingface.co/datasets/ggerganov/whisper.cpp

## Installation

1. Copy the contents of this directory to `config/programs/asr/whisper-cpp/`
2. Run `script/setup.py`
3. Download a model with `script/download.py`
    * Example: `script/download.py en_tiny`
    * Models are downloaded to `config/data/asr/whisper-cpp` directory
4. Test with `script/wav2text`
    * Example `script/wav2text /path/to/ggml-tiny.en.bin /path/to/test.wav`
