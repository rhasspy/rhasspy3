# Pocketsphinx

Speech to text service for Rhasspy based on [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx).


## Installation

1. Copy the contents of this directory to `config/programs/asr/pocketsphinx/`
2. Run `script/setup`
3. Download a model with `script/download.py`
    * Example: `script/download.py en_cmu`
    * Models are downloaded to `share` directory
4. Test with `script/wav2text`
    * Example `script/wav2text share/en-us_pocketsphinx-cmu/ /path/to/test.wav`
