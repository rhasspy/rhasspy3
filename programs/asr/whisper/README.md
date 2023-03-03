# Whisper

Speech to text service for Rhasspy based on [Whisper](https://github.com/openai/whisper).

Models are downloaded automatically the first time they're used to the `config/data/asr/whisper` directory.

Available models:

* tiny.en
* tiny
* base.en
* base
* small.en
* small
* medium.en
* medium
* large-v1
* large-v2
* large

## Installation

1. Copy the contents of this directory to `config/programs/asr/whisper/`
2. Run `script/setup`
3. Test with `script/wav2text`
    * Example `script/wav2text 'tiny.en' /path/to/test.wav`
