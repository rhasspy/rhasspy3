# Pocketsphinx

Speech to text service for Rhasspy based on [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx).

Additional models can be downloaded here: https://github.com/synesthesiam/voice2json-profiles

Model directories should have this layout:

* model/
    * acoustic_model/
    * dictionary.txt
    * language_model.txt
    
These correspond to the `-hmm`, `-dict`, and `-lm` decoder arguments.

## Installation

1. Copy the contents of this directory to `config/programs/asr/pocketsphinx/`
2. Run `script/setup`
3. Download a model with `script/download.py`
    * Example: `script/download.py en_cmu`
    * Models are downloaded to `config/data/asr/pocketsphinx` directory
4. Test with `script/wav2text`
    * Example `script/wav2text /path/to/en-us_pocketsphinx-cmu/ /path/to/test.wav`
