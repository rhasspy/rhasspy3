FROM python:3.11-bullseye

COPY script/ ./script/
COPY programs/ ./programs/

RUN script/install_program wake openwakeword-lite

COPY etc/hey_rhasspy.wav ./
COPY bin/ ./bin/
COPY wyoming/ ./wyoming/
COPY rhasspy3/ ./rhasspy3/

RUN bin/wav_to_raw.py --rate 16000 --width 2 --channels 1 < hey_rhasspy.wav | \
    script/run bin/wake_detect_stream.py --wake-program openwakeword-lite | \
    python3 -c 'import json; import sys; assert json.load(sys.stdin)["type"] == "detection"'
