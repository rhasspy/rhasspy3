"""Utilities for creating processes."""
import asyncio
import logging
import os
import shlex
import string
from asyncio.subprocess import PIPE, Process
from typing import Optional, Union

from .config import CommandConfig, PipelineProgramConfig, ProgramConfig
from .core import Rhasspy
from .util import merge_dict

_LOGGER = logging.getLogger(__name__)


class MissingProgramConfigError(Exception):
    pass


class ProcessContextManager:
    """Wrapper for an async process that terminates on exit."""

    def __init__(self, proc: Process, name: str):
        self.proc = proc
        self.name = name

    async def __aenter__(self):
        return self.proc

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self.proc.returncode is None:
                self.proc.terminate()
                await self.proc.wait()
        except ProcessLookupError:
            # Expected when process has already exited
            pass
        except Exception:
            _LOGGER.exception("Unexpected error stopping process: %s", self.name)


async def create_process(
    rhasspy: Rhasspy, domain: str, name: Union[str, PipelineProgramConfig]
) -> ProcessContextManager:
    pipeline_config: Optional[PipelineProgramConfig] = None
    if isinstance(name, PipelineProgramConfig):
        pipeline_config = name
        name = pipeline_config.name

    assert name, f"No program name for domain {domain}"

    # The "." is special in program names:
    # it means to use the directory of "base" in <base>.<name>.
    #
    # This is used for <base>.client programs, which are just scripts in the
    # "base" directory that communicate with their respective servers.
    if "." in name:
        base_name = name.split(".", maxsplit=1)[0]
    else:
        base_name = name

    program_config: Optional[ProgramConfig] = rhasspy.config.programs.get(
        domain, {}
    ).get(name)
    assert program_config is not None, f"No config for program {domain}/{name}"
    assert isinstance(program_config, ProgramConfig)

    # Directory where this program is installed
    program_dir = rhasspy.programs_dir / domain / base_name

    # Directory where this program should store data
    data_dir = rhasspy.data_dir / domain / base_name

    # ${variables} available within program/pipeline template_args
    default_mapping = {
        "program_dir": str(program_dir.absolute()),
        "data_dir": str(data_dir.absolute()),
    }

    command_str = program_config.command.strip()
    command_mapping = dict(default_mapping)
    if program_config.template_args:
        # Substitute within program template args
        args_mapping = dict(program_config.template_args)
        for arg_name, arg_str in args_mapping.items():
            arg_template = string.Template(arg_str)
            args_mapping[arg_name] = arg_template.safe_substitute(default_mapping)

        command_mapping.update(args_mapping)

    if pipeline_config is not None:
        if pipeline_config.template_args:
            # Substitute within pipeline template args
            args_mapping = dict(pipeline_config.template_args)
            for arg_name, arg_str in args_mapping.items():
                arg_template = string.Template(arg_str)
                args_mapping[arg_name] = arg_template.safe_substitute(default_mapping)

            merge_dict(command_mapping, args_mapping)

    # Substitute template args
    command_template = string.Template(command_str)
    command_str = command_template.safe_substitute(command_mapping)

    working_dir = rhasspy.programs_dir / domain / base_name
    env = dict(os.environ)

    # Add rhasspy3/bin to $PATH
    env["PATH"] = f'{rhasspy.base_dir}/bin:${env["PATH"]}'

    # Ensure stdout is flushed for Python programs
    env["PYTHONUNBUFFERED"] = "1"

    cwd = working_dir if working_dir.is_dir() else None

    if program_config.shell:
        if program_config.adapter:
            program, *args = shlex.split(program_config.adapter)
            args.append("--shell")
            args.append(command_str)

            _LOGGER.debug("(shell): %s %s", program, args)
            proc = await asyncio.create_subprocess_exec(
                program,
                *args,
                stdin=PIPE,
                stdout=PIPE,
                cwd=cwd,
                env=env,
            )
        else:
            _LOGGER.debug("(shell): %s %s", program, args)
            proc = await asyncio.create_subprocess_shell(
                command_str,
                stdin=PIPE,
                stdout=PIPE,
                cwd=cwd,
                env=env,
            )
    else:
        if program_config.adapter:
            program, *args = shlex.split(program_config.adapter)
            args.append(command_str)
        else:
            program, *args = shlex.split(command_str)

        _LOGGER.debug("%s %s", program, args)
        proc = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdin=PIPE,
            stdout=PIPE,
            cwd=cwd,
            env=env,
        )

    return ProcessContextManager(proc, name=name)


async def run_command(rhasspy: Rhasspy, command_config: CommandConfig) -> int:
    env = dict(os.environ)

    # Add rhasspy3/bin to $PATH
    env["PATH"] = f'{rhasspy.base_dir}/bin:${env["PATH"]}'

    # Ensure stdout is flushed for Python programs
    env["PYTHONUNBUFFERED"] = "1"

    if command_config.shell:
        proc = await asyncio.create_subprocess_shell(
            command_config.command,
            env=env,
        )
    else:
        program, *args = shlex.split(command_config.command)
        proc = await asyncio.create_subprocess_exec(
            program,
            *args,
            env=env,
        )

    await proc.wait()
    assert proc.returncode is not None

    return proc.returncode
