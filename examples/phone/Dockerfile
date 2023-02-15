
FROM debian:bullseye as build
ARG TARGETARCH
ARG TARGETVARIANT

ENV LANG C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

RUN echo "Dir::Cache var/cache/apt/${TARGETARCH}${TARGETVARIANT};" > /etc/apt/apt.conf.d/01cache

RUN --mount=type=cache,id=apt-build,target=/var/cache/apt \
    mkdir -p /var/cache/apt/${TARGETARCH}${TARGETVARIANT}/archives/partial && \
    apt-get update && \
    apt-get install --yes --no-install-recommends \
      python3 python3-venv python3-pip \
      gstreamer1.0-tools gstreamer1.0-plugins-good

WORKDIR /rhasspy3

COPY setup.py requirements_http_api.txt ./
COPY rhasspy3/ ./rhasspy3/
COPY rhasspy3_http_api/ ./rhasspy3_http_api/
COPY script/ ./script/

ENV venv=/rhasspy3/.venv

RUN --mount=type=cache,id=pip-build,target=/root/.cache/pip \
    script/setup_http_server

# vad
COPY programs/vad/silero/ ./config/programs/vad/silero/
RUN --mount=type=cache,id=pip-build,target=/root/.cache/pip \
    config/programs/vad/silero/script/setup

# tts
COPY programs/tts/larynx2/ ./config/programs/tts/larynx2/
COPY config/programs/tts/larynx2/share/ ./config/programs/tts/larynx2/share/
COPY config/programs/tts/larynx2/bin/ ./config/programs/tts/larynx2/bin/

# asr
COPY programs/asr/faster-whisper/ ./config/programs/asr/faster-whisper/
RUN --mount=type=cache,id=pip-build,target=/root/.cache/pip \
    config/programs/asr/faster-whisper/script/setup
COPY config/programs/asr/faster-whisper/share/tiny-int8/ \
     config/programs/asr/faster-whisper/share/tiny-int8/


# handle
COPY programs/handle/home_assistant_conversation/ \
    ./config/programs/handle/home_assistant_conversation/
COPY config/programs/handle/home_assistant_conversation/etc/ \
    ./config/programs/handle/home_assistant_conversation/etc/

COPY bin/ ./bin/
COPY examples/phone/sip.py ./
COPY examples/phone/configuration.yaml ./config/

COPY examples/phone/run.sh ./

# HTTP
EXPOSE 13331

# RTP
EXPOSE 5004

# SIP
EXPOSE 5060

ENTRYPOINT ["./run.sh"]
