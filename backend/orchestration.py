"""Coordinate the two agent stages and preserve source data for presentation."""

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)

JSONObject = dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    arguments: JSONObject
    result: JSONObject


CallTool = Callable[[str, JSONObject, str], Awaitable[JSONObject]]
RunAgentOne = Callable[[str, CallTool], Awaitable[Sequence[str]]]
RunAgentTwo = Callable[
    [tuple[str, ...], tuple[ToolResult, ...]],
    Awaitable[Mapping[int, JSONObject]],
]
InvokeTool = Callable[[str, JSONObject], Awaitable[JSONObject]]
ValidateUI = Callable[[JSONObject], None]


async def orchestrate(
    request: str,
    run_agent_one: RunAgentOne,
    run_agent_two: RunAgentTwo,
    invoke_tool: InvokeTool,
    *,
    validate_ui: ValidateUI | None = None,
) -> JSONObject:
    """Run curation and attach any validated matching UI after the answer.

    Agent one awaits its tool calls, provides a unique call ID per call, and
    returns ordered, renderable text sections. Tool errors propagate to that
    agent so its adapter can choose an appropriate conversational response.
    Agent two receives those sections and an independent snapshot of each
    successful call, in invocation order. It proposes UI by zero-based section
    index. Each proposal must carry the original section as fallback_text for
    validation. Only sections fully represented by a validated card are
    omitted from the visible text. They remain available as card fallbacks.
    """
    calls: dict[str, ToolResult | None] = {}

    async def call_tool(name: str, arguments: JSONObject, call_id: str) -> JSONObject:
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("A tool call ID must be a nonempty string")
        if call_id in calls:
            raise ValueError("A tool call ID may only be used once")
        calls[call_id] = None
        saved_arguments = deepcopy(arguments)
        result = await invoke_tool(name, deepcopy(saved_arguments))
        calls[call_id] = ToolResult(call_id, name, saved_arguments, deepcopy(result))
        return deepcopy(result)

    curated = await run_agent_one(request, call_tool)
    if isinstance(curated, (str, bytes)):
        raise TypeError("Agent one must return a sequence of text sections")
    sections = tuple(curated)
    if any(not isinstance(section, str) for section in sections):
        raise TypeError("Agent one must return text for each section")

    handoff = tuple(deepcopy(call) for call in calls.values() if call is not None)
    try:
        proposed = await run_agent_two(sections, handoff)
    except Exception:
        logger.warning("Presentation stage failed", exc_info=True)
        proposed = {}

    supplements: dict[int, JSONObject] = {}
    covered_sections: set[int] = set()
    if isinstance(proposed, Mapping):
        for index, result in proposed.items():
            if type(index) is not int or not 0 <= index < len(sections):
                continue
            if _is_choice_result(result, sections[index]):
                supplements[index] = {key: deepcopy(result[key]) for key in ("type", "choice", "label", "actions")}
                continue
            if not isinstance(result, dict):
                continue
            covered = result.get("covers_section") is True
            card = {key: value for key, value in result.items() if key != "covers_section"}
            if not _is_ui_result(card, sections[index]):
                continue
            try:
                if validate_ui is not None:
                    validate_ui(deepcopy(card))
            except Exception:
                logger.warning("UI result validation failed for section %d", index)
                continue
            supplements[index] = {"type": "ui", **deepcopy(card)}
            if covered and index != 0:
                covered_sections.add(index)

    blocks = [{"type": "text", "text": section} for index, section in enumerate(sections)
              if index not in covered_sections]
    blocks.extend(supplements[index] for index in sorted(supplements))
    return {"blocks": blocks}


def _is_choice_result(result: object, fallback: str) -> bool:
    return (
        isinstance(result, dict) and result.get("type") == "actions"
        and result.get("choice") is True and result.get("fallback_text") == fallback
        and isinstance(result.get("label"), str)
        and isinstance(result.get("actions"), list) and 2 <= len(result["actions"]) <= 8
        and all(isinstance(action, dict) and all(
            isinstance(action.get(key), str) and bool(action[key].strip())
            for key in ("id", "label", "message")
        ) for action in result["actions"])
    )


def _is_ui_result(result: object, fallback: str) -> bool:
    return (
        isinstance(result, dict)
        and set(result) == {"component", "code", "props", "fallback_text"}
        and isinstance(result["component"], str)
        and bool(result["component"].strip())
        and isinstance(result["code"], str)
        and bool(result["code"].strip())
        and isinstance(result["props"], dict)
        and isinstance(result["fallback_text"], str)
        and result["fallback_text"] == fallback
    )
