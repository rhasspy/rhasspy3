import io
import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import IO, Deque, Optional, Union

from .asr import DOMAIN as ASR_DOMAIN
from .asr import Transcript, transcribe
from .config import PipelineConfig, PipelineProgramConfig
from .core import Rhasspy
from .event import Event, async_read_event
from .handle import Handled, NotHandled, handle
from .intent import Intent, NotRecognized, recognize
from .mic import DOMAIN as MIC_DOMAIN
from .program import create_process
from .snd import play
from .tts import synthesize
from .util.dataclasses_json import DataClassJsonMixin
from .vad import segment
from .wake import Detection, detect

_LOGGER = logging.getLogger(__name__)


@dataclass
class PipelineResult(DataClassJsonMixin):
    wake_detection: Optional[Detection] = None
    asr_transcript: Optional[Transcript] = None
    intent_result: Optional[Union[Intent, NotRecognized]] = None
    handle_result: Optional[Union[Handled, NotHandled]] = None


class StopAfterDomain(str, Enum):
    WAKE = "wake"
    ASR = "asr"
    INTENT = "intent"
    HANDLE = "handle"
    TTS = "tts"


async def run(
    rhasspy: Rhasspy,
    pipeline: Union[str, PipelineConfig],
    samples_per_chunk: int,
    asr_chunks_to_buffer: int = 0,
    mic_program: Optional[Union[str, PipelineProgramConfig]] = None,
    wake_program: Optional[Union[str, PipelineProgramConfig]] = None,
    wake_detection: Optional[Detection] = None,
    asr_program: Optional[Union[str, PipelineProgramConfig]] = None,
    asr_wav_in: Optional[IO[bytes]] = None,
    asr_transcript: Optional[Transcript] = None,
    vad_program: Optional[Union[str, PipelineProgramConfig]] = None,
    intent_result: Optional[Union[Intent, NotRecognized]] = None,
    intent_program: Optional[Union[str, PipelineProgramConfig]] = None,
    handle_result: Optional[Union[Handled, NotHandled]] = None,
    handle_program: Optional[Union[str, PipelineProgramConfig]] = None,
    tts_wav_in: Optional[IO[bytes]] = None,
    tts_program: Optional[Union[str, PipelineProgramConfig]] = None,
    snd_program: Optional[Union[str, PipelineProgramConfig]] = None,
    stop_after: Optional[StopAfterDomain] = None,
    play_sleep: bool = True,
) -> PipelineResult:
    pipeline_result = PipelineResult()

    if isinstance(pipeline, str):
        pipeline = rhasspy.config.pipelines[pipeline]

    mic_program = mic_program or pipeline.mic
    wake_program = wake_program or pipeline.wake
    asr_program = asr_program or pipeline.asr
    vad_program = vad_program or pipeline.vad
    intent_program = intent_program or pipeline.intent
    handle_program = handle_program or pipeline.handle
    tts_program = tts_program or pipeline.tts
    snd_program = snd_program or pipeline.snd

    # Speech to text
    if asr_wav_in is not None:
        if stop_after == StopAfterDomain.WAKE:
            return pipeline_result

        asr_wav_in.seek(0)
        assert asr_program is not None, "No asr program"
        asr_transcript = await transcribe(
            rhasspy, asr_program, asr_wav_in, samples_per_chunk
        )
    elif asr_transcript is None:
        assert mic_program is not None, "No asr program"

        if wake_program is None:
            assert asr_program is not None, "No asr program"
            assert vad_program is not None, "No vad program"
            await _mic_asr(
                rhasspy, mic_program, asr_program, vad_program, pipeline_result
            )
            return pipeline_result

        # Audio input, wake word detection, segmentation, speech to text
        if stop_after == StopAfterDomain.WAKE:
            assert wake_program is not None, "No vad program"
            await _mic_wake(
                rhasspy,
                mic_program,
                wake_program,
                pipeline_result,
                wake_detection=wake_detection,
            )
            return pipeline_result

        assert wake_program is not None, "No vad program"
        assert asr_program is not None, "No asr program"
        assert vad_program is not None, "No vad program"
        await _mic_wake_asr(
            rhasspy,
            mic_program,
            wake_program,
            asr_program,
            vad_program,
            pipeline_result,
            asr_chunks_to_buffer=asr_chunks_to_buffer,
            wake_detection=wake_detection,
        )

        asr_transcript = pipeline_result.asr_transcript
        pipeline_result.asr_transcript = asr_transcript

    if (stop_after == StopAfterDomain.ASR) or (
        (intent_program is None) and (handle_program is None)
    ):
        return pipeline_result

    # Text to intent
    if (asr_transcript is not None) and (intent_program is not None):
        pipeline_result.asr_transcript = asr_transcript
        intent_result = await recognize(
            rhasspy, intent_program, asr_transcript.text or ""
        )
        pipeline_result.intent_result = intent_result

    # Handle intent
    handle_input: Optional[Union[Intent, NotRecognized, Transcript]] = None
    if intent_result is not None:
        pipeline_result.intent_result = intent_result
        handle_input = intent_result
    elif asr_transcript is not None:
        handle_input = asr_transcript

    if (stop_after == StopAfterDomain.INTENT) or (handle_program is None):
        return pipeline_result

    if (handle_input is not None) and (handle_result is None):
        assert handle_program is not None, "Pipeline is missing handle"
        handle_result = await handle(rhasspy, handle_program, handle_input)
        pipeline_result.handle_result = handle_result

    if (stop_after == StopAfterDomain.HANDLE) or (tts_program is None):
        return pipeline_result

    # Text to speech
    if handle_result is not None:
        pipeline_result.handle_result = handle_result
        if handle_result.text:
            assert tts_program is not None, "Pipeline is missing tts"
            tts_wav_in = io.BytesIO()
            await synthesize(rhasspy, tts_program, handle_result.text, tts_wav_in)
        else:
            _LOGGER.debug("No text returned from handle")

    if (stop_after == StopAfterDomain.TTS) or (snd_program is None):
        return pipeline_result

    # Audio output
    if tts_wav_in is not None:
        tts_wav_in.seek(0)
        assert snd_program is not None, "Pipeline is missing snd"
        await play(rhasspy, snd_program, tts_wav_in, samples_per_chunk, play_sleep)

    return pipeline_result


async def _mic_wake(
    rhasspy: Rhasspy,
    mic_program: Union[str, PipelineProgramConfig],
    wake_program: Union[str, PipelineProgramConfig],
    pipeline_result: PipelineResult,
    wake_detection: Optional[Detection] = None,
):
    async with (await create_process(rhasspy, MIC_DOMAIN, mic_program)) as mic_proc:
        assert mic_proc.stdout is not None
        if wake_detection is None:
            wake_detection = await detect(
                rhasspy,
                wake_program,
                mic_proc.stdout,
            )

        if wake_detection is not None:
            pipeline_result.wake_detection = wake_detection
        else:
            _LOGGER.debug("run: no wake word detected")


async def _mic_asr(
    rhasspy: Rhasspy,
    mic_program: Union[str, PipelineProgramConfig],
    asr_program: Union[str, PipelineProgramConfig],
    vad_program: Union[str, PipelineProgramConfig],
    pipeline_result: PipelineResult,
    asr_chunks_to_buffer: int = 0,
):
    async with (await create_process(rhasspy, MIC_DOMAIN, mic_program)) as mic_proc, (
        await create_process(rhasspy, ASR_DOMAIN, asr_program)
    ) as asr_proc:
        assert mic_proc.stdout is not None
        assert asr_proc.stdin is not None
        assert asr_proc.stdout is not None

        await segment(
            rhasspy,
            vad_program,
            mic_proc.stdout,
            asr_proc.stdin,
        )
        while True:
            asr_event = await async_read_event(asr_proc.stdout)
            if asr_event is None:
                break

            if Transcript.is_type(asr_event.type):
                pipeline_result.asr_transcript = Transcript.from_event(asr_event)
                break


async def _mic_wake_asr(
    rhasspy: Rhasspy,
    mic_program: Union[str, PipelineProgramConfig],
    wake_program: Union[str, PipelineProgramConfig],
    asr_program: Union[str, PipelineProgramConfig],
    vad_program: Union[str, PipelineProgramConfig],
    pipeline_result: PipelineResult,
    asr_chunks_to_buffer: int = 0,
    wake_detection: Optional[Detection] = None,
):
    chunk_buffer: Optional[Deque[Event]] = (
        deque(maxlen=asr_chunks_to_buffer) if asr_chunks_to_buffer > 0 else None
    )

    async with (await create_process(rhasspy, MIC_DOMAIN, mic_program)) as mic_proc, (
        await create_process(rhasspy, ASR_DOMAIN, asr_program)
    ) as asr_proc:
        assert mic_proc.stdout is not None
        assert asr_proc.stdin is not None
        assert asr_proc.stdout is not None

        if wake_detection is None:
            wake_detection = await detect(
                rhasspy, wake_program, mic_proc.stdout, chunk_buffer
            )

        if wake_detection is not None:
            pipeline_result.wake_detection = wake_detection
            await segment(
                rhasspy,
                vad_program,
                mic_proc.stdout,
                asr_proc.stdin,
                chunk_buffer,
            )
            while True:
                asr_event = await async_read_event(asr_proc.stdout)
                if asr_event is None:
                    break

                if Transcript.is_type(asr_event.type):
                    pipeline_result.asr_transcript = Transcript.from_event(asr_event)
                    break
        else:
            _LOGGER.debug("run: no wake word detected")
