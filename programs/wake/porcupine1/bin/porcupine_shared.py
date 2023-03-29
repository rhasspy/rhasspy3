import argparse
from pathlib import Path
from typing import List, Tuple

import pvporcupine


def get_arg_parser() -> argparse.ArgumentParser:
    """Get shared command-line argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        required=True,
        action="append",
        nargs="+",
        help="Keyword model settings (path, [sensitivity])",
    )
    parser.add_argument(
        "--lang_model",
        help="Path of the language model (.pv file), default is English",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    return parser


def load_porcupine(args: argparse.Namespace) -> Tuple[pvporcupine.Porcupine, List[str]]:
    """Loads porcupine keywords. Returns Porcupine object and list of keyword names (in order)."""
    # Path to embedded keywords
    keyword_dir = Path(next(iter(pvporcupine.pv_keyword_paths("").values()))).parent

    names: List[str] = []
    keyword_paths: List[Path] = []
    sensitivities: List[float] = []

    model_path = (
        str(Path(args.lang_model).absolute()) if args.lang_model is not None else None
    )

    for model_settings in args.model:
        keyword_path_str = model_settings[0]
        keyword_path = Path(keyword_path_str)
        if not keyword_path.exists():
            keyword_path = keyword_dir / keyword_path_str
            assert keyword_path.exists(), f"Cannot find {keyword_path_str}"

        keyword_paths.append(keyword_path)
        names.append(keyword_path.stem)

        sensitivity = 0.5
        if len(model_settings) > 1:
            sensitivity = float(model_settings[1])

        sensitivities.append(sensitivity)

    porcupine = pvporcupine.create(
        keyword_paths=[str(keyword_path.absolute()) for keyword_path in keyword_paths],
        sensitivities=sensitivities,
        model_path=model_path,
    )

    return porcupine, names
