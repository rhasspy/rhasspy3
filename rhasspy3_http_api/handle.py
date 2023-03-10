import argparse
import json
import logging
from typing import Optional, Union

from quart import Quart, Response, jsonify, request

from rhasspy3.asr import Transcript
from rhasspy3.config import PipelineConfig
from rhasspy3.core import Rhasspy
from rhasspy3.event import Event
from rhasspy3.handle import handle
from rhasspy3.intent import Intent, NotRecognized

_LOGGER = logging.getLogger(__name__)
_HANDLE_INPUT_TYPES = (Transcript, Intent, NotRecognized)


def add_handle(
    app: Quart, rhasspy: Rhasspy, pipeline: PipelineConfig, args: argparse.Namespace
) -> None:
    @app.route("/handle/handle", methods=["GET", "POST"])
    async def http_handle_handle() -> Response:
        """Handle text or intent JSON."""
        if request.method == "GET":
            data = request.args["input"]
        else:
            data = (await request.data).decode()

        handle_pipeline = (
            rhasspy.config.pipelines[request.args["pipeline"]]
            if "pipeline" in request.args
            else pipeline
        )

        # Input can be plain text or a JSON intent
        handle_input: Optional[Union[Intent, NotRecognized, Transcript]] = None
        if request.content_type == "application/json":
            # Try to parse either an "intent" or "not-recognized" event
            event = Event(json.loads(data))
            for event_class in _HANDLE_INPUT_TYPES:
                assert issubclass(event_class, _HANDLE_INPUT_TYPES)
                if event_class.is_type(event.type):
                    handle_input = event_class.from_event(event)
        else:
            # Assume plain text
            handle_input = Transcript(data)

        assert handle_input is not None, "Invalid input"

        handle_program = request.args.get("handle_program") or handle_pipeline.handle
        assert handle_program is not None, "Missing program for handle"
        _LOGGER.debug("handle: handle=%s, input='%s'", handle_program, handle_input)

        result = await handle(rhasspy, handle_program, handle_input)
        _LOGGER.debug("handle: result=%s", result)

        return jsonify(result.event().to_dict() if result is not None else {})
