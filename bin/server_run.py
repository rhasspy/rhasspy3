#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import shlex
import string
import subprocess
from typing import Union, List

from rhasspy3.core import Rhasspy
from rhasspy3.util import merge_dict

_LOGGER = logging.getLogger("server_run")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Configuration directory",
    )
    parser.add_argument("domain", help="Domain of server (asr, tts, etc.)")
    parser.add_argument("server", help="Name of server to run")

    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    server = rhasspy.config.servers[args.domain][args.server]

    command_str = server.command
    mapping = server.template_args or {}

    if server.template_args:
        merge_dict(mapping, server.template_args)

    if mapping:
        command_template = string.Template(command_str)
        command_str = command_template.safe_substitute(mapping)

    env = dict(os.environ)

    # Add rhasspy3/bin to $PATH
    env["PATH"] = f'{rhasspy.base_dir}/bin:${env["PATH"]}'

    # Ensure stdout is flushed for Python programs
    env["PYTHONUNBUFFERED"] = "1"

    server_dir = rhasspy.config_dir / "programs" / args.domain / args.server
    cwd = server_dir if server_dir.is_dir() else rhasspy.base_dir

    if server.shell:
        command: Union[str, List[str]] = command_str
    else:
        command = shlex.split(command_str)

    _LOGGER.debug(command)
    proc = subprocess.Popen(command, shell=server.shell, cwd=cwd, env=env)
    with proc:
        sys.exit(proc.wait())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
