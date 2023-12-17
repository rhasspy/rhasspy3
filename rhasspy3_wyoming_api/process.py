#!/usr/bin/env python3
import asyncio
import logging
from typing import Dict

from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.program import create_process
from rhasspy3.asr import DOMAIN as ASR_DOMAIN
from rhasspy3.tts import DOMAIN as TTS_DOMAIN

_LOGGER = logging.getLogger(__name__)


class PipelineProcessManager:
    """Manager of running pipeline processes."""

    def __init__(self, rhasspy: Rhasspy, pipeline: PipelineConfig):
        self.rhasspy = rhasspy
        self.pipeline = pipeline
        self.processes: Dict[str, "asyncio.subprocess.Process"] = {}
        self.processes_lock = {ASR_DOMAIN: asyncio.Lock(), TTS_DOMAIN: asyncio.Lock()}

    async def get_process(self, domain: str) -> "asyncio.subprocess.Process":
        """Get a running Piper process or start a new one if necessary."""
        proc = self.processes.get(domain)
        if (proc is None) or (proc.returncode is not None):
            # Remove if stopped
            self.processes.pop(domain, None)

            # Start new process
            _LOGGER.debug("Starting process for: %s", domain)

            if domain == ASR_DOMAIN:
                program = self.pipeline.asr
            elif domain == TTS_DOMAIN:
                program = self.pipeline.tts
            else:
                raise RuntimeError("Unsupported domain")

            if program is None:
                raise RuntimeError(f"No {domain} program")

            _LOGGER.debug("Starting %s process: %s", domain, program)

            proc = await (
                await create_process(self.rhasspy, domain, program)
            ).__aenter__()

            self.processes[domain] = proc

        return proc

    async def terminate_process(self, domain: str):
        proc = self.processes.get(domain)
        if proc is None:
            return

        try:
            if proc.returncode is None:
                proc.terminate()
                await proc.communicate()
        except ProcessLookupError:
            # Expected when process has already exited
            pass
        except Exception:
            _LOGGER.exception("Unexpected error stopping process for: %s", domain)
