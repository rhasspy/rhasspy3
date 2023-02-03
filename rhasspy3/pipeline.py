import io
import logging
from collections import deque
from dataclasses import dataclass
from typing import IO, Deque, Optional, Union

from .asr import DOMAIN as ASR_DOMAIN
from .asr import Transcript, transcribe
from .config import PipelineConfig
from .core import Rhasspy
from .event import Event, async_read_event
from .handle import Handled, NotHandled, handle
from .intent import Intent, NotRecognized, recognize
from .mic import DOMAIN as MIC_DOMAIN
from .program import create_process
from .snd import play
from .tts import synthesize
from .vad import segment
from .wake import Detection, detect

_LOGGER = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    wake_wav_bytes: Optional[bytes] = None
    wake_detection: Optional[Detection] = None
    asr_wav_bytes: Optional[bytes] = None
    asr_transcript: Optional[Transcript] = None
    intent_result: Optional[Union[Intent, NotRecognized]] = None
    handle_result: Optional[Union[Handled, NotHandled]] = None
    tts_wav_bytes: Optional[bytes] = None


async def run(
    rhasspy: Rhasspy,
    pipeline: Union[str, PipelineConfig],
    samples_per_chunk: int,
    asr_chunks_to_buffer: int = 0,
    wake_detection: Optional[Detection] = None,
    asr_wav_in: Optional[IO[bytes]] = None,
    asr_transcript: Optional[Transcript] = None,
    intent_result: Optional[Union[Intent, NotRecognized]] = None,
    handle_result: Optional[Union[Handled, NotHandled]] = None,
    tts_wav_in: Optional[IO[bytes]] = None,
    play_sleep: bool = True,
) -> PipelineResult:
    pipeline_result = PipelineResult()

    if isinstance(pipeline, str):
        pipeline = rhasspy.config.pipelines[pipeline]

    # Speech to text
    if asr_wav_in is not None:
        pipeline_result.asr_wav_bytes = asr_wav_in.read()
        asr_wav_in.seek(0)
        assert pipeline.asr is not None, "Pipeline is missing asr"
        asr_transcript = await transcribe(
            rhasspy, pipeline.asr, asr_wav_in, samples_per_chunk
        )
    else:
        # Audio input, wake word detection, segmentation, speech to text
        await _mic_wake_asr(
            rhasspy,
            pipeline,
            pipeline_result,
            asr_chunks_to_buffer=asr_chunks_to_buffer,
            wake_detection=wake_detection,
        )
        asr_transcript = pipeline_result.asr_transcript

    # Text to intent
    if (asr_transcript is not None) and (pipeline.intent is not None):
        pipeline_result.asr_transcript = asr_transcript
        intent_result = await recognize(
            rhasspy, pipeline.intent, asr_transcript.text or ""
        )

    # Handle intent
    handle_input: Optional[Union[Intent, NotRecognized, Transcript]] = None
    if intent_result is not None:
        pipeline_result.intent_result = intent_result
        handle_input = intent_result
    elif asr_transcript is not None:
        handle_input = asr_transcript

    if handle_input is not None:
        assert pipeline.handle is not None, "Pipeline is missing handle"
        handle_result = await handle(rhasspy, pipeline.handle, handle_input)

    # Text to speech
    if handle_result is not None:
        pipeline_result.handle_result = handle_result
        if handle_result.text:
            assert pipeline.tts is not None, "Pipeline is missing tts"
            tts_wav_in = io.BytesIO()
            await synthesize(rhasspy, pipeline.tts, handle_result.text, tts_wav_in)
        else:
            _LOGGER.debug("No text returned from handle")

    # Audio output
    if tts_wav_in is not None:
        pipeline_result.tts_wav_bytes = tts_wav_in.read()
        tts_wav_in.seek(0)
        assert pipeline.snd is not None, "Pipeline is missing snd"
        await play(rhasspy, pipeline.snd, tts_wav_in, samples_per_chunk, play_sleep)

    return pipeline_result


async def _mic_wake_asr(
    rhasspy: Rhasspy,
    pipeline: PipelineConfig,
    pipeline_result: PipelineResult,
    asr_chunks_to_buffer: int = 0,
    wake_detection: Optional[Detection] = None,
):
    chunk_buffer: Optional[Deque[Event]] = (
        deque(maxlen=asr_chunks_to_buffer) if asr_chunks_to_buffer > 0 else None
    )

    assert pipeline.mic is not None, "Pipeline is missing mic"
    assert pipeline.wake is not None, "Pipeline is missing wake"
    assert pipeline.vad is not None, "Pipeline is missing vad"
    assert pipeline.asr is not None, "Pipeline is missing asr"

    async with (await create_process(rhasspy, MIC_DOMAIN, pipeline.mic)) as mic_proc, (
        await create_process(rhasspy, ASR_DOMAIN, pipeline.asr)
    ) as asr_proc:
        if wake_detection is None:
            wake_detection = await detect(
                rhasspy, pipeline.wake, mic_proc.stdout, chunk_buffer
            )

        if wake_detection is not None:
            pipeline_result.wake_detection = wake_detection
            await segment(
                rhasspy,
                pipeline.vad,
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
