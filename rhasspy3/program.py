import asyncio
import logging
import shlex
import os
import string
from asyncio import subprocess
from typing import Optional, Union

from .core import Rhasspy
from .config import ProgramConfig, FlowProgramConfig
from .util import merge_dict

_LOGGER = logging.getLogger(__name__)


class MissingProgramConfigError(Exception):
    pass


async def create_process(
    rhasspy: Rhasspy, domain: str, name: Union[str, FlowProgramConfig]
) -> subprocess.Process:
    flow_config: Optional[FlowProgramConfig] = None
    if isinstance(name, FlowProgramConfig):
        flow_config = name
        name = flow_config.name

    program_config = rhasspy.config.programs.get(domain, {}).get(name, {})
    assert program_config is not None, f"No config for program {domain}/{name}"
    assert isinstance(program_config, ProgramConfig)

    command_str = program_config.command.strip()
    if flow_config is not None:
        if flow_config.template_args:
            command_template = string.Template(command_str)
            if program_config.template_args:
                mapping = dict(program_config.template_args)
                merge_dict(mapping, flow_config.template_args)
            else:
                mapping = flow_config.template_args

            command_str = command_template.safe_substitute(mapping)

    working_dir = rhasspy.config_dir / "programs" / domain / name
    env = dict(os.environ)

    # Add rhasspy3/bin to $PATH
    env["PATH"] = f'{rhasspy.base_dir}/bin:${env["PATH"]}'

    # Ensure stdout is flushed for Python programs
    env["PYTHONUNBUFFERED"] = "1"

    create_args = dict(
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        cwd=working_dir if working_dir.is_dir() else None,
        env=env,
    )

    if program_config.shell:
        if program_config.wrapper:
            program, *args = shlex.split(program_config.wrapper)
            args.append("--shell")
            args.append(command_str)
            proc = await asyncio.create_subprocess_exec(program, *args, **create_args)
        else:
            proc = await asyncio.create_subprocess_shell(command_str, **create_args)
    else:
        if program_config.wrapper:
            program, *args = shlex.split(program_config.wrapper)
            args.append(command_str)
        else:
            program, *args = shlex.split(command_str)

        proc = await asyncio.create_subprocess_exec(program, *args, **create_args)

    return proc
