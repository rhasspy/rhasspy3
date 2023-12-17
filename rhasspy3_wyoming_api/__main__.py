import argparse
import asyncio
import logging
from functools import partial
from pathlib import Path

from wyoming.info import (
    Attribution,
    Info,
    TtsProgram,
    TtsVoice,
    AsrProgram,
    AsrModel,
    WakeProgram,
    WakeModel,
    HandleProgram,
    HandleModel,
    IntentProgram,
    IntentModel,
)
from wyoming.server import AsyncServer

from rhasspy3.core import Rhasspy

from .handler import PipelineEventHandler
from .process import PipelineProcessManager

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("rhasspy")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument(
        "--pipeline", default="default", help="Name of default pipeline to run"
    )
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    parser.add_argument(
        "--language",
        default=["en"],
        action="append",
        help="Reported language (may be used repeatedly)",
    )
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    pipeline = rhasspy.config.pipelines[args.pipeline]

    wyoming_info = Info(
        tts=[] if pipeline.tts is None else [
            TtsProgram(
                name=pipeline.tts.name,
                description=f"Rhasspy3 {args.pipeline} pipeline TTS program",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/"
                ),
                installed=True,
                voices=[
                    TtsVoice(
                        name="default",
                        description="Pipeline-defined voice",
                        attribution=Attribution(
                            name="rhasspy", url="https://github.com/rhasspy"
                        ),
                        installed=True,
                        languages=args.language,
                    )
                ],
            )
        ],
        asr=[] if pipeline.asr is None else [
            AsrProgram(
                name=pipeline.asr.name,
                description=f"Rhasspy3 {args.pipeline} pipeline ASR program",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/"
                ),
                installed=True,
                models=[
                    AsrModel(
                        name="default",
                        description="Pipeline-defined model",
                        attribution=Attribution(
                            name="rhasspy",
                            url="https://github.com/rhasspy/",
                        ),
                        installed=True,
                        languages=args.language,
                    )
                ],
            )
        ],
        wake=[] if pipeline.wake is None else [
            WakeProgram(
                name=pipeline.wake.name,
                description=f"Rhasspy3 {args.pipeline} pipeline wake program",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/"
                ),
                installed=True,
                models=[
                    WakeModel(
                        name="default",
                        description="Pipeline-defined model",
                        attribution=Attribution(
                            name="rhasspy",
                            url="https://github.com/rhasspy/",
                        ),
                        installed=True,
                        languages=args.language,
                    )
                ],
            )
        ],
        handle=[] if pipeline.handle is None else [
            HandleProgram(
                name=pipeline.handle.name,
                description=f"Rhasspy3 {args.pipeline} pipeline handle program",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/"
                ),
                installed=True,
                models=[
                    HandleModel(
                        name="default",
                        description="Pipeline-defined model",
                        attribution=Attribution(
                            name="rhasspy",
                            url="https://github.com/rhasspy/",
                        ),
                        installed=True,
                        languages=args.language,
                    )
                ],
            )
        ],
        intent=[] if pipeline.intent is None else [
            IntentProgram(
                name=pipeline.intent.name,
                description=f"Rhasspy3 {args.pipeline} pipeline intent program",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/"
                ),
                installed=True,
                models=[
                    IntentModel(
                        name="default",
                        description="Pipeline-defined model",
                        attribution=Attribution(
                            name="rhasspy",
                            url="https://github.com/rhasspy/",
                        ),
                        installed=True,
                        languages=args.language,
                    )
                ],
            )
        ],
    )

    process_manager = PipelineProcessManager(rhasspy, pipeline)

    # Start server
    server = AsyncServer.from_uri(args.uri)

    _LOGGER.info("Ready")
    await server.run(
        partial(
            PipelineEventHandler,
            wyoming_info,
            process_manager,
        )
    )


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
