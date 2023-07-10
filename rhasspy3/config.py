import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .util import merge_dict
from .util.dataclasses_json import DataClassJsonMixin
from .util.jaml import safe_load


@dataclass
class CommandConfig(DataClassJsonMixin):
    command: str
    shell: bool = False


@dataclass
class ProgramConfig(CommandConfig):
    adapter: Optional[str] = None
    template_args: Optional[Dict[str, Any]] = None
    installed: bool = True


@dataclass
class PipelineProgramConfig(DataClassJsonMixin):
    name: str
    template_args: Optional[Dict[str, Any]] = None
    adapter_args: Optional[str] = None
    after: Optional[CommandConfig] = None


@dataclass
class PipelineConfig(DataClassJsonMixin):
    inherit: Optional[str] = None
    mic: Optional[PipelineProgramConfig] = None
    wake: Optional[PipelineProgramConfig] = None
    vad: Optional[PipelineProgramConfig] = None
    asr: Optional[PipelineProgramConfig] = None
    intent: Optional[PipelineProgramConfig] = None
    handle: Optional[PipelineProgramConfig] = None
    tts: Optional[PipelineProgramConfig] = None
    snd: Optional[PipelineProgramConfig] = None


@dataclass
class SatelliteConfig(DataClassJsonMixin):
    mic: Optional[PipelineProgramConfig] = None
    mic_filter: Optional[PipelineProgramConfig] = None
    wake: Optional[PipelineProgramConfig] = None
    remote: Optional[PipelineProgramConfig] = None
    snd: Optional[PipelineProgramConfig] = None
    vad: Optional[PipelineProgramConfig] = None


@dataclass
class ServerConfig(DataClassJsonMixin):
    command: str
    shell: bool = False
    template_args: Optional[Dict[str, Any]] = None


@dataclass
class Config(DataClassJsonMixin):
    programs: Dict[str, Dict[str, ProgramConfig]]
    """domain -> name -> program"""

    pipelines: Dict[str, PipelineConfig] = field(default_factory=dict)
    """name -> pipeline"""

    satellites: Dict[str, SatelliteConfig] = field(default_factory=dict)
    """name -> satellite"""

    servers: Dict[str, Dict[str, ServerConfig]] = field(default_factory=dict)
    """domain -> name -> server"""

    def __post_init__(self):
        # Handle inheritance
        # TODO: Catch loops
        pipeline_queue = list(self.pipelines.values())
        while pipeline_queue:
            child_pipeline = pipeline_queue.pop()
            if child_pipeline.inherit:
                parent_pipeline = self.pipelines[child_pipeline.inherit]
                if parent_pipeline.inherit:
                    # Need to process parent first
                    pipeline_queue.append(child_pipeline)
                    continue

                child_pipeline.mic = child_pipeline.mic or parent_pipeline.mic
                child_pipeline.wake = child_pipeline.wake or parent_pipeline.wake
                child_pipeline.vad = child_pipeline.vad or parent_pipeline.vad
                child_pipeline.asr = child_pipeline.asr or parent_pipeline.asr
                child_pipeline.intent = child_pipeline.intent or parent_pipeline.intent
                child_pipeline.handle = child_pipeline.handle or parent_pipeline.handle
                child_pipeline.tts = child_pipeline.tts or parent_pipeline.tts
                child_pipeline.snd = child_pipeline.snd or parent_pipeline.snd

                # Mark as done
                child_pipeline.inherit = None


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="+", help="Path to YAML configuration file")
    args = parser.parse_args()

    config_dict: Dict[str, Any] = {}
    for config_path in args.config:
        with open(config_path, "r", encoding="utf-8") as config_file:
            merge_dict(config_dict, safe_load(config_file))

    config = Config.from_dict(config_dict)
    print(config)
