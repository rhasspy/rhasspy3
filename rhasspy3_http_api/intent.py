import argparse
import logging

from quart import Response, request, Quart, jsonify

from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.intent import recognize, Intent

_LOGGER = logging.getLogger(__name__)


def add_intent(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/api/text-to-intent", methods=["GET", "POST"])
    async def api_text_to_intent() -> Response:
        if request.method == "GET":
            text = request.args["text"]
        else:
            text = (await request.data).decode()

        program = request.args.get("program", pipeline.intent)
        _LOGGER.debug("text-to-intent: intent=%s, text='%s'", program, text)

        result = await recognize(rhasspy, program, text)
        _LOGGER.debug("text-to-intent: result=%s", result)

        data = {}
        if isinstance(result, Intent):
            data = result.to_rhasspy()

        return jsonify(data)
