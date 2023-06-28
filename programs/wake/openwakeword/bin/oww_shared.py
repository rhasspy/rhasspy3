import argparse

from openwakeword import Model


def get_arg_parser() -> argparse.ArgumentParser:
    """Get shared command-line argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--trigger-level", type=int, default=4)
    parser.add_argument("--refractory-level", type=int, default=30)
    parser.add_argument("--samples-per-chunk", type=int, default=1280)
    #
    parser.add_argument(
        "--model",
        required=True,
        action="append",
        help="Name or path of openWakeWord model",
    )
    parser.add_argument(
        "--vad-threshold",
        type=float,
        help="Whether to use a voice activity detection model (VAD)",
    )
    parser.add_argument(
        "--custom-verifier-model",
        action="append",
        nargs=2,
        metavar=("oww_name", "verifier_path"),
    )
    parser.add_argument("--custom-verifier-threshold", type=float)
    parser.add_argument("--inference-framework", choices=("tflite", "onnx"))
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    return parser


def load_openwakeword(
    args: argparse.Namespace,
) -> Model:
    """Loads openWakeWord with the supplied options."""
    kwargs = {}
    if args.vad_threshold is not None:
        kwargs["vad_threshold"] = args.vad_threshold

    if args.custom_verifier_threshold is not None:
        kwargs["custom_verifier_threshold"] = args.custom_verifier_threshold

    if args.custom_verifier_model:
        kwargs["custom_verifier_models"] = dict(args.custom_verifier_model)

    if args.inference_framework is not None:
        kwargs["inference_framework"] = args.inference_framework

    return Model(wakeword_models=args.model, **kwargs)
