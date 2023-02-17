import argparse
import logging

from quart import Quart, Response, jsonify, request

from rhasspy3.config import PipelineConfig
from rhasspy3.core import Rhasspy
from rhasspy3.intent import recognize

_LOGGER = logging.getLogger(__name__)


def add_intent(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/intent/recognize", methods=["GET", "POST"])
    async def http_intent_recognize() -> Response:
        """Recognize intent from text."""
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        intent_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )
        intent_program = request.args.get("intent_program") or intent_pipeline.intent
        assert intent_program, "Missing program for intent"
        _LOGGER.debug("recognize: intent=%s, text='%s'", intent_program, text)

        result = await recognize(rhasspy, intent_program, text)
        _LOGGER.debug("recognize: result=%s", result)

        return jsonify(result.event().to_dict() if result is not None else {})
