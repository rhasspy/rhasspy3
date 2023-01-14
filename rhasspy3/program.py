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
            args.append(program_config.command.strip())
            proc = await asyncio.create_subprocess_exec(program, *args, **create_args)
        else:
            cmd = program_config.command.strip()
            proc = await asyncio.create_subprocess_shell(cmd, **create_args)
    else:
        if program_config.wrapper:
            program, *args = shlex.split(program_config.wrapper)
            args.append(program_config.command.strip())
        else:
            program, *args = shlex.split(program_config.command)

        proc = await asyncio.create_subprocess_exec(program, *args, **create_args)

    return proc
