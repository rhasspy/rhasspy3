#!/usr/bin/env python3
import argparse
import logging
import shlex
import string
import subprocess
from pathlib import Path

from rhasspy3.core import Rhasspy

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    parser.add_argument("program")
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    program_config = rhasspy.config.programs.get(args.domain, {}).get(args.program)
    assert program_config is not None, f"No config for {args.domain} {args.program}"

    install = program_config.install
    assert install is not None, f"No install config for {args.domain} {args.program}"

    program_dir = rhasspy.programs_dir / args.domain / args.program
    data_dir = rhasspy.data_dir / args.domain / args.program

    default_mapping = {
        "program_dir": str(program_dir.absolute()),
        "data_dir": str(data_dir.absolute()),
    }

    # Check if already installed
    if install.check_file is not None:
        check_file = Path(
            string.Template(install.check_file).safe_substitute(default_mapping)
        )
        if check_file.exists():
            _LOGGER.info("Installed: %s", check_file)
            return

    install_command = string.Template(install.command).safe_substitute(default_mapping)
    _LOGGER.debug(install_command)

    cwd = program_dir if program_dir.exists() else rhasspy.config_dir

    if install.shell:
        subprocess.check_call(install_command, shell=True, cwd=cwd)
    else:
        subprocess.check_call(shlex.split(install_command), cwd=cwd)


if __name__ == "__main__":
    main()
