#!/usr/bin/env bash

ip="$1"
if [ -z "${ip}" ]; then
    echo "Add IP address as argument"
    exit 1
fi

python3 sip.py "${ip}" &
script/http_server --server asr faster-whisper --server tts larynx2 &

while [ ! -e 'config/programs/asr/faster-whisper/var/run/faster-whisper.socket' ];
do
    sleep 0.1;
done

while [ ! -e 'config/programs/tts/larynx2/var/run/larynx2.socket' ];
do
    sleep 0.1;
done

script/run bin/pipeline_run.py --debug --loop
