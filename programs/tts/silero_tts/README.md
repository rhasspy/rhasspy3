# Silero TTS

Text to speech service for Rhasspy based on [Silero TTS](https://github.com/snakers4/silero-models).

## Installation

1. Copy the contents of this directory to `config/programs/tts/silero_tts/`
2. Run `script/setup`
3. Download a model with `script/download`
    * Example: `script/download --language ru --model v3_1_ru`
    * Models are downloaded to `config/data/tts/silero_tts/models` directory
4. Test with `bin/tts_synthesize.py`
    *
    Example `script/run bin/tts_synthesize.py --tts-program silero_tts -f test.wav --debug 'test text!'`
