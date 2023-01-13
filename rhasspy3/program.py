import asyncio
import logging
import shlex
import os
from asyncio import subprocess

from .core import Rhasspy
from .config import ProgramConfig

_LOGGER = logging.getLogger(__name__)


class MissingProgramConfigError(Exception):
    pass


async def create_process(
    rhasspy: Rhasspy, domain: str, name: str
) -> subprocess.Process:
    program_config = rhasspy.config.programs.get(domain, {}).get(name, {})
    assert program_config is not None, f"No config for program {domain}/{name}"

    assert isinstance(program_config, ProgramConfig)

    if program_config.wrapper:
        program, *args = shlex.split(program_config.wrapper)
        args.append(program_config.command.strip())
    else:
        program, *args = shlex.split(program_config.command)

    working_dir = rhasspy.config_dir / "programs" / domain / name

    env = dict(os.environ)

    # Add rhasspy3/bin to $PATH
    env["PATH"] = f'{rhasspy.base_dir}/bin:${env["PATH"]}'

    # Ensure stdout is flushed for Python programs
    env["PYTHONUNBUFFERED"] = "1"

    proc = await asyncio.create_subprocess_exec(
        program,
        *args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        cwd=working_dir if working_dir.is_dir() else None,
        env=env,
    )

    return proc
