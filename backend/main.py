"""Local FastAPI entry point for the vehicle discovery milestone."""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Annotated, Literal
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

from .conversation import curate, selection_for, filter_records, requests_test_drive
from .appointments import test_drive
from .openai_runtime import OpenAIRuntimeError
from starlette.concurrency import run_in_threadpool

from .orchestration import CallTool, RunAgentOne, RunAgentTwo, orchestrate
from .presentation import DiscoveryPresentation
from .registry import ToolRegistry
from .settings import load_settings
from .response_contract import greeting_response, shopping_message, decorate_response

logger = logging.getLogger(__name__)
project_root = Path(__file__).resolve().parents[1]


class CatalogPresentationRequest(BaseModel):
    tool_name: Literal[
        "render_car_details", "render_color_options", "render_vehicle_gallery",
        "render_vehicle_visualization", "render_financing_offers",
    ]
    arguments: dict


class TestDriveRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=100)
    requested_date: date
    requested_time: time


class TranscriptMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20000)


class VehicleAction(BaseModel):
    intent: Literal["details", "colors", "color_preview", "photos", "rotation", "financing"]
    model_id: str = Field(min_length=1, max_length=100)
    trim_id: str | None = Field(default=None, max_length=160)
    color_id: str | None = Field(default=None, max_length=220)


class ComparisonAction(BaseModel):
    intent: Literal["comparison"]
    trim_ids: tuple[Annotated[str, Field(min_length=1, max_length=160)],
                    Annotated[str, Field(min_length=1, max_length=160)]]


VEHICLE_ACTION_TOOLS = {
    "details": ("get_car_details", "render_car_details"),
    "colors": ("get_vehicle_media", "render_color_options"),
    "color_preview": ("get_car_details", "render_car_details"),
    "photos": ("get_vehicle_media", "render_vehicle_gallery"),
    "rotation": ("get_vehicle_media", "render_vehicle_visualization"),
    "financing": ("get_financing_offers", "render_financing_offers"),
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    vehicle_action: Annotated[VehicleAction | ComparisonAction, Field(discriminator="intent")] | None = None
    transcript: list[TranscriptMessage] = Field(default_factory=list, max_length=40)
    history: list[Annotated[str, Field(max_length=2000)]] = Field(default_factory=list, max_length=40)


async def curate_discovery(message: str, call_tool: CallTool) -> list[str]:
    return await curate(message, call_tool)


def create_app(
    run_agent_one: RunAgentOne = curate_discovery,
    run_agent_two: RunAgentTwo | None = None,
    *,
    offline_catalog: bool = False,
    test_drive_enabled: bool = True,
) -> FastAPI:
    registry = ToolRegistry(project_root)
    presentation = run_agent_two
    if presentation is None:
        presentation = DiscoveryPresentation(project_root).select
    service = FastAPI(title="Adaptive UI")
    dist = project_root / "frontend" / "dist"

    @service.post("/catalog/presentation")
    def catalog_presentation(body: CatalogPresentationRequest) -> dict:
        from .ui_registry import UIRegistry
        from .orchestration import ToolResult
        from jsonschema.exceptions import ValidationError

        names = {
            "render_car_details": "get_car_details",
            "render_financing_offers": "get_financing_offers",
        }
        name = names.get(body.tool_name, "get_vehicle_media")
        arguments = dict(body.arguments)
        if name == "get_financing_offers":
            arguments["as_of"] = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
        try:
            result = registry.invoke(name, arguments)
            if not result["records"]:
                return {"blocks": [{"type": "text", "text": "No matching published information is available."}]}
            source = ToolResult("catalog-action", name, arguments, result)
            block = UIRegistry(project_root).render(
                body.tool_name, source, list(range(len(result["records"]))),
                "The requested vehicle information could not be displayed.",
            )
            caveats = {
                "render_color_options": "Confirm paint availability, price, and interior combinations for your selected trim.",
                "render_vehicle_gallery": "Images retain their published model-year and trim applicability.",
                "render_vehicle_visualization": "Interactive rotation requires verified images for the selected configuration.",
                "render_financing_offers": "Published terms are subject to expiry, eligibility, and lender approval. Estimates do not establish credit approval.",
            }
            warnings = caveats.get(body.tool_name)
            blocks = [{"id": "catalog-card", "type": "ui", "role": "card", **block}]
            if warnings:
                blocks.append({"id": "catalog-notice", "type": "text", "role": "notice", "text": warnings})
            return {"blocks": blocks}
        except (ValueError, ValidationError):
            raise HTTPException(status_code=422, detail="The requested model or configuration is unavailable.") from None

    @service.get("/catalog/models")
    def catalog_models() -> list[dict]:
        result = registry.invoke("search_cars", {"model_year": 2027})
        return [{"id": row["model_id"], "name": row["name"], "year": 2027} for row in result["records"]]

    @service.post("/test-drive-requests")
    def submit_test_drive(body: TestDriveRequest, response: Response) -> dict:
        if not test_drive_enabled:
            raise HTTPException(status_code=503, detail="Contact the dealership to request a test drive.")
        try:
            response.headers["Cache-Control"] = "no-store"
            return test_drive(project_root, **body.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @service.get("/capabilities")
    def capabilities() -> dict:
        settings = load_settings(project_root)
        return {
            "ai_configured": bool(settings.get("OPENAI_API_KEY")),
            "catalog_year": 2027,
            "test_drive_enabled": test_drive_enabled,
        }

    @service.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        index = dist / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Build the local frontend first.")
        return FileResponse(index)

    if (dist / "assets").is_dir():
        service.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @service.post("/chat")
    async def chat(body: ChatRequest, response: Response) -> dict:
        response.headers["Cache-Control"] = "no-store"
        standard = run_agent_one is curate_discovery
        greeting = greeting_response(body.message) if standard else None
        if offline_catalog and greeting is not None:
            return greeting
        message = shopping_message(body.message) if standard else body.message
        candidates = []

        async def invoke_tool(name: str, arguments: dict) -> dict:
            result = await run_in_threadpool(registry.invoke, name, arguments)
            if name == "search_cars":
                candidates.extend(result["records"])
            return result

        user_history = [item.content for item in body.transcript if item.role == "user"] if body.transcript else body.history

        async def contextual_curate(message: str, call_tool: CallTool) -> list[str]:
            return await curate(message, call_tool, user_history)

        async def contextual_present(sections, calls):
            selection = selection_for(message, user_history)
            from .ui_registry import UIRegistry
            presentations = {
                "details": "render_car_details", "colors": "render_color_options",
                "comparison": "render_car_comparison",
                "gallery": "render_vehicle_gallery", "financing": "render_financing_offers",
                "visualization": "render_vehicle_visualization",
            }
            sources = [call for call in calls if call.name != "search_cars"]
            if len(sections) in (2, 3) and sources and selection.mode in presentations:
                source = sources[-1]
                card = UIRegistry(project_root).render(
                    presentations[selection.mode], source,
                    list(range(len(source.result["records"]))), sections[1],
                )
                return {1: {**card, "covers_section": True}}
            replacements = await DiscoveryPresentation(project_root).select(
                sections, calls, record_filter=lambda records: filter_records(records, selection)
            )
            for block in replacements.values():
                block["covers_section"] = True
                if selection.mode == "comparison":
                    block["props"]["startComparison"] = True
            return replacements

        first_stage = contextual_curate if run_agent_one is curate_discovery else run_agent_one
        second_stage = contextual_present if run_agent_one is curate_discovery and run_agent_two is None else presentation
        settings = load_settings(project_root)
        runtime = None
        if standard and not offline_catalog:
            if not settings.get("OPENAI_API_KEY"):
                raise HTTPException(status_code=503, detail="The AI assistant is not configured.",
                                    headers={"Cache-Control": "no-store"})
            from .openai_runtime import OpenAIRuntime
            from .ui_registry import UIRegistry

            runtime = OpenAIRuntime(
                project_root, api_key=settings["OPENAI_API_KEY"],
                model=settings["OPENAI_MODEL"], render_ui=UIRegistry(project_root).render,
                test_drive_enabled=test_drive_enabled,
            )

            async def ai_curate(message, call_tool):
                history = [item.model_dump() for item in body.transcript] or body.history
                return await runtime.curate(message, call_tool, history)

            first_stage, second_stage = ai_curate, runtime.select

            if body.vehicle_action is not None and standard and not offline_catalog:
                action = body.vehicle_action
                intent = action.intent
                color_id = action.color_id if isinstance(action, VehicleAction) else None
                if intent == "colors" and color_id:
                    intent = "color_preview"
                if isinstance(action, ComparisonAction):
                    if len(set(action.trim_ids)) != 2:
                        raise HTTPException(status_code=422, detail="Select two distinct configurations.")
                    domain_tool, ui_tool = "compare_cars", "render_car_comparison"
                    arguments = {"trim_ids": list(action.trim_ids)}
                else:
                    domain_tool, ui_tool = VEHICLE_ACTION_TOOLS[intent]
                    arguments = {"model_id": action.model_id}
                    if action.trim_id:
                        arguments["trim_id"] = action.trim_id
                    if action.intent == "financing":
                        arguments["as_of"] = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
                async def curate_vehicle_action(prompt, call_tool):
                    try:
                        result = await call_tool(domain_tool, arguments, "vehicle-selection")
                    except ValueError:
                        raise HTTPException(status_code=422, detail="Invalid vehicle selection.") from None
                    records = result["records"]
                    selected_color = next(
                        (color for record in records for color in record.get("colors", [])
                         if color["color_id"] == color_id), None
                    )
                    if ((color_id or intent == "color_preview") and
                            (intent != "color_preview" or selected_color is None)):
                        raise HTTPException(status_code=422, detail="Invalid color selection.")
                    return await runtime.vehicle_action_reply(prompt, intent, records, selected_color)

                async def present_vehicle_action(sections, calls):
                    source = calls[0]
                    if not source.result["records"]:
                        return {}
                    for record in source.result["records"]:
                        if color_id:
                            record["selected_color_id"] = color_id
                        if isinstance(action, ComparisonAction):
                            details = await invoke_tool("get_car_details", {"model_id": record["model_id"]})
                            record["configuration_choices"] = details["records"][0]["trims"]
                    if isinstance(action, VehicleAction) and action.intent == "details" and action.trim_id:
                        # Keep the full selector while using exact trim data on display.
                        all_details = await invoke_tool("get_car_details", {"model_id": action.model_id})
                        source.result["records"][0]["trims"] = all_details["records"][0]["trims"]
                        source.result["records"][0]["selected_trim_id"] = action.trim_id
                    card = UIRegistry(project_root).render(
                        ui_tool, source, list(range(len(source.result["records"]))), sections[1],
                    )
                    return {1: {**card, "covers_section": True}}

                first_stage, second_stage = curate_vehicle_action, present_vehicle_action

        try:
            async with asyncio.timeout(110):
                result = await orchestrate(message, first_stage, second_stage, invoke_tool)
                if runtime is not None and runtime.web_blocks is not None:
                    for block, web_block in zip(result["blocks"], runtime.web_blocks):
                        block["citations"] = web_block["citations"]
                if greeting is not None:
                    generated = decorate_response(result, message, user_history)
                    generated["blocks"].extend(
                        block for block in greeting["blocks"] if block["type"] != "text"
                    )
                    return generated
                if not standard:
                    return result
                response_body = decorate_response(result, message, user_history, candidates=candidates)
                if test_drive_enabled and body.vehicle_action is None and requests_test_drive(message):
                    response_body["blocks"].append({
                        "id": "test-drive-demo", "type": "actions", "label": "Test drive",
                        "actions": [{"id": "open-test-drive", "label": "Open test-drive demo",
                                     "message": "Open the test-drive demo.", "open_test_drive": True}],
                    })
                if isinstance(body.vehicle_action, ComparisonAction) and any(
                    block.get("component") == "CarComparison" for block in response_body["blocks"]
                ):
                    # Text-derived filters like FWD describe only one side of this exact pair.
                    response_body["blocks"] = [
                        block for block in response_body["blocks"] if block["type"] != "context"
                    ]
                return response_body
        except HTTPException:
            raise
        except OpenAIRuntimeError as error:
            logger.warning("Chat model failure (%s): %s", error.status_code, error)
            raise HTTPException(status_code=error.status_code, detail=str(error),
                                headers={"Cache-Control": "no-store"}) from None
        except TimeoutError:
            logger.warning("Chat request exceeded the server deadline")
            raise HTTPException(status_code=504, detail="The assistant request timed out.",
                                headers={"Cache-Control": "no-store"}) from None
        except Exception as error:
            logger.error("Chat processing failed (%s)", type(error).__name__)
            raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable. Please retry.",
                                headers={"Cache-Control": "no-store"}) from None

    return service


app = create_app()
