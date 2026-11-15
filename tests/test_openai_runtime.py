import json
import unittest
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import httpx

from backend.openai_runtime import OpenAIRuntime, OpenAIRuntimeError
from backend.orchestration import ToolResult

ROOT = Path(__file__).resolve().parents[1]


def complete(value):
    return {
        "status": "completed",
        "output": [{
            "type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": json.dumps(value)}],
        }],
    }


def tool_response(call_id="call-1", arguments=None):
    return {
        "status": "completed",
        "output": [
            {"type": "reasoning", "id": "reason-1", "summary": [], "encrypted_content": "encrypted-fixture"},
            {"type": "function_call", "name": "search_cars", "call_id": call_id,
             "arguments": json.dumps(arguments or {"model_year": 2027})},
        ],
    }


class OpenAIRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_loop_replays_reasoning_results_and_history(self):
        requests = []
        raw = {"records": [{"model_id": "fixture", "url": "https://example.invalid/a?x=1&x=2",
                           "nested": {"empty": [], "null": None}}]}
        responses = [tool_response(), complete({"sections": ["Before", "Car", "After"]})]

        def transport(request):
            requests.append(json.loads(request.content))
            self.assertEqual(request.headers["Authorization"], "Bearer fixture-only")
            return httpx.Response(200, json=responses.pop(0))

        calls = []
        async def invoke(name, arguments, call_id):
            calls.append((name, arguments, call_id))
            return deepcopy(raw)

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            result = await runtime.curate("show it", invoke, [
                {"role": "user", "content": "CX-5"},
                {"role": "assistant", "content": "Here is the CX-5."},
            ])
        self.assertEqual(result, ["Before", "Car", "After"])
        self.assertEqual(calls, [("search_cars", {"model_year": 2027}, "call-1")])
        self.assertFalse(requests[0]["store"])
        self.assertIn(datetime.now(ZoneInfo("America/Chicago")).date().isoformat(), requests[0]["instructions"])
        self.assertIn("Never guess IDs", requests[0]["instructions"])
        self.assertTrue(all(tool["strict"] is False for tool in requests[0]["tools"]))
        self.assertEqual(requests[1]["input"][-3]["encrypted_content"], "encrypted-fixture")
        self.assertEqual(json.loads(requests[1]["input"][-1]["output"]), raw)
        self.assertEqual(requests[0]["input"][1]["role"], "assistant")

    async def test_invalid_tool_arguments_never_reach_registry(self):
        responses = [tool_response(arguments={"model_year": 2027, "unknown": "value"}),
                     complete({"sections": ["Please clarify."]})]
        requests = []

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=responses.pop(0))

        async def invoke(*args):
            self.fail("Invalid arguments reached local registry")

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            await runtime.curate("fixture", invoke)
        self.assertIn("error", json.loads(requests[1]["input"][-1]["output"]))

    async def test_round_limit_and_duplicate_call_ids(self):
        async def invoke(*args):
            return {"records": []}

        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=tool_response())
        )) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client, max_rounds=1)
            with self.assertRaisesRegex(OpenAIRuntimeError, "round limit"):
                await runtime.curate("fixture", invoke)
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            with self.assertRaisesRegex(OpenAIRuntimeError, "invalid tool reference"):
                await runtime.curate("fixture", invoke)

    async def test_failure_messages_do_not_expose_key_or_response_body(self):
        async def invoke(*args):
            self.fail("Tool invocation was unexpected")

        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(status, text="sensitive-service-detail")
                )) as client:
                    runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="sensitive-fixture-key", client=client)
                    with self.assertRaises(OpenAIRuntimeError) as caught:
                        await runtime.curate("fixture", invoke)
                    self.assertNotIn("sensitive", str(caught.exception))

        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "incomplete", "output": []})
        )) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            with self.assertRaisesRegex(OpenAIRuntimeError, "incomplete"):
                await runtime.curate("fixture", invoke)
        runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="")
        with self.assertRaisesRegex(OpenAIRuntimeError, "not been configured"):
            await runtime.curate("fixture", invoke)

    async def test_selection_receives_complete_raw_sources_and_rejects_bad_refs(self):
        raw = {"records": [{"id": "a", "metadata": {"null": None, "empty": []}},
                           {"id": "b", "url": "https://example.invalid/image?a=1&a=2"}],
               "extra": {"not_in_prose": True}}
        call = ToolResult("source-1", "search_cars", {"model_year": 2027}, raw)
        base = {"section_index": 1, "tool_name": "render_car_list",
                "source_call_id": "source-1", "record_indices": [1], "covers_section": True}
        requests = []
        proposals = [base, {**base, "section_index": 0, "source_call_id": "unknown"},
                     {**base, "section_index": 2, "record_indices": [3]},
                     {**base, "section_index": 2, "tool_name": "made_up"},
                     {**base, "section_index": 2, "record_indices": [1, 1]}]

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=complete({"choices": [], "replacements": proposals}))

        rendered = []
        def renderer(name, source, indices, fallback):
            rendered.append((name, source, indices, fallback))
            source.result["extra"]["not_in_prose"] = False
            return {"component": "CarList", "code": "fixture", "props": {"id": "b"},
                    "fallback_text": fallback}

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client, render_ui=renderer)
            result = await runtime.select(("before", "middle", "after"), (call,))
        self.assertEqual(list(result), [1])
        self.assertEqual(len(rendered), 1)
        self.assertEqual(rendered[0][2:], ([1], "middle"))
        handoff = json.loads(requests[0]["input"][0]["content"])
        self.assertEqual(handoff["tool_results"][0]["result"], raw)
        self.assertTrue(raw["extra"]["not_in_prose"])

    async def test_model_selection_cannot_supply_generated_props(self):
        response = complete({"choices": [], "replacements": [{
            "section_index": 0, "tool_name": "render_car_list", "source_call_id": "source",
            "record_indices": [0], "covers_section": True, "props": {"price": 1},
        }]})
        call = ToolResult("source", "search_cars", {}, {"records": [{"id": "a"}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=response)
        )) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client,
                                    render_ui=lambda *args: self.fail("Invalid output rendered"))
            with self.assertRaisesRegex(OpenAIRuntimeError, "invalid response"):
                await runtime.select(("middle",), (call,))

    async def test_network_timeout_is_safe(self):
        def transport(request):
            raise httpx.ReadTimeout("sensitive-transport-detail", request=request)

        async def invoke(*args):
            self.fail("Timed-out request should not invoke tools")

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            with self.assertRaisesRegex(OpenAIRuntimeError, "timed out") as caught:
                await runtime.curate("fixture", invoke)
            self.assertNotIn("sensitive", str(caught.exception))

    async def test_tool_failure_is_returned_to_model_without_internal_details(self):
        requests = []
        responses = [tool_response(), complete({"sections": ["The data is unavailable."]})]

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=responses.pop(0))

        async def invoke(*args):
            raise RuntimeError("/private/internal-fixture-path")

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            sections = await runtime.curate("fixture", invoke)
        self.assertEqual(sections, ["The data is unavailable."])
        serialized = json.dumps(requests[1])
        self.assertNotIn("/private/internal-fixture-path", serialized)
        self.assertIn("local tool could not complete", serialized)

    async def test_detail_answer_retries_until_exact_trim_tool_succeeds(self):
        model_id = "us-2027-cx5"
        trim_id = "us-2027-cx5-2-5-s-preferred-suv-awd-6at-2r"
        raw = {"records": [{
            "model_id": model_id, "model_family": "cx5", "powertrain": "gasoline",
            "trims": [{"trim_id": trim_id, "name": "2.5 S Preferred"}],
        }]}
        detail = {
            "status": "completed",
            "output": [{"type": "function_call", "name": "get_car_details", "call_id": "detail-1",
                        "arguments": json.dumps({"model_id": model_id, "trim_id": trim_id})}],
        }
        responses = [
            tool_response(),
            complete({"sections": ["Unverified Preferred details"]}),
            detail,
            complete({"sections": ["Verified Preferred details"]}),
        ]
        requests = []
        invoked = []

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=responses.pop(0))

        async def invoke(name, arguments, call_id):
            invoked.append((name, arguments))
            return deepcopy(raw)

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            result = await runtime.curate("Tell me about 2027 CX-5 Preferred", invoke)
        self.assertEqual(result, ["Verified Preferred details"])
        self.assertEqual([name for name, _ in invoked], ["search_cars", "get_car_details"])
        self.assertIn("cannot be accepted", requests[2]["input"][-1]["content"])
        self.assertEqual(len({request["instructions"] for request in requests}), 1)
        self.assertNotIn("Unverified Preferred details", json.dumps(requests[2]["input"]))
        constrained = next(tool for tool in requests[2]["tools"] if tool["name"] == "get_car_details")
        self.assertEqual(constrained["parameters"]["properties"]["trim_id"]["enum"], [trim_id])

    async def test_shortened_trim_id_is_rejected_with_exact_id_feedback(self):
        model_id = "us-2027-cx5"
        trim_id = "us-2027-cx5-2-5-s-preferred-suv-awd-6at-2r"
        raw = {"records": [{
            "model_id": model_id, "model_family": "cx5", "powertrain": "gasoline",
            "trims": [{"trim_id": trim_id, "name": "2.5 S Preferred"}],
        }]}
        def details(call_id, identifier):
            return {
                "status": "completed",
                "output": [{"type": "function_call", "name": "get_car_details", "call_id": call_id,
                            "arguments": json.dumps({"model_id": model_id, "trim_id": identifier})}],
            }
        responses = [tool_response(), details("bad-detail", "us-2027-cx5-2-5-s-preferred"),
                     details("good-detail", trim_id), complete({"sections": ["Verified details"]})]
        requests = []
        invoked = []

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=responses.pop(0))

        async def invoke(name, arguments, call_id):
            invoked.append((name, arguments))
            return deepcopy(raw)

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            await runtime.curate("Tell me about 2027 CX-5 Preferred", invoke)
        self.assertEqual(len(invoked), 2)
        self.assertEqual(invoked[-1][1]["trim_id"], trim_id)
        feedback = json.loads(requests[2]["input"][-1]["output"])
        self.assertEqual(feedback["allowed_trim_ids"], [trim_id])
        self.assertEqual(feedback["requested_trim_ids"], [trim_id])

    async def test_detailed_source_prevents_broad_search_card_replacement(self):
        model = {"model_id": "us-2027-cx5"}
        calls = (
            ToolResult("search", "search_cars", {}, {"records": [model]}),
            ToolResult("detail", "get_car_details", {"trim_id": "preferred"}, {"records": [model]}),
        )
        proposals = [
            {"section_index": 1, "tool_name": "render_car_list",
             "source_call_id": "search", "record_indices": [0], "covers_section": True},
            {"section_index": 1, "tool_name": "render_car_details",
             "source_call_id": "detail", "record_indices": [0], "covers_section": True},
        ]
        rendered = []

        def renderer(name, source, indices, fallback):
            rendered.append((name, source.call_id))
            return {"component": "VehicleDetails", "code": "fixture", "props": {},
                    "fallback_text": fallback}

        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=complete({"choices": [], "replacements": proposals}))
        )) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client, render_ui=renderer)
            result = await runtime.select(("before", "Preferred trim details", "after"), calls)
        self.assertEqual(rendered, [("render_car_details", "detail")])
        self.assertEqual(result[1]["component"], "VehicleDetails")

    async def test_phev_followup_limits_cards_without_dropping_raw_sources(self):
        records = [
            {"model_id": "cx5", "model_family": "cx5", "powertrain": "gasoline"},
            {"model_id": "cx90-mhev", "model_family": "cx90", "powertrain": "mild_hybrid"},
            {"model_id": "cx90-phev", "model_family": "cx90", "powertrain": "plug_in_hybrid"},
        ]
        raw = {"records": records, "metadata": {"untouched": [None, ""]}}
        proposals = {"choices": [], "replacements": [{
            "section_index": 1, "tool_name": "render_car_list",
            "source_call_id": "source", "record_indices": [0, 1, 2], "covers_section": True,
        }]}
        responses = [complete({"sections": ["Here is the plug-in option.", "CX-90 Plug-in Hybrid", "Caveat"]}),
                     complete(proposals)]
        requests = []
        rendered = []

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=responses.pop(0))

        async def invoke(*args):
            self.fail("The fixture curation returns final prose without tools")

        def renderer(name, source, indices, fallback):
            rendered.append((deepcopy(source.result), indices))
            return {"component": "CarList", "code": "fixture", "props": {}, "fallback_text": fallback}

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client, render_ui=renderer)
            sections = await runtime.curate(
                "Which of those is a plug-in hybrid?", invoke,
                [{"role": "user", "content": "Show me Mazda SUVs"},
                 {"role": "assistant", "content": "CX-5, CX-90 Inline 6 Turbo, CX-90 Plug-in Hybrid"}],
            )
            await runtime.select(tuple(sections), (ToolResult("source", "search_cars", {}, raw),))
        self.assertEqual(rendered[0][1], [2])
        self.assertEqual(rendered[0][0], raw)
        handoff = json.loads(requests[1]["input"][0]["content"])
        self.assertEqual(handoff["tool_results"][0]["result"], raw)
        self.assertEqual(handoff["eligible_record_indices"], {"source": [2]})

    async def test_color_section_retains_text_instead_of_generic_gallery(self):
        call = ToolResult("media", "get_vehicle_media", {}, {
            "records": [{"model_id": "cx5", "colors": [{"name": "Black leather"}], "assets": []}]
        })
        proposal = {"choices": [], "replacements": [{
            "section_index": 1, "tool_name": "render_vehicle_gallery",
            "source_call_id": "media", "record_indices": [0], "covers_section": False,
        }]}
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=complete(proposal))
        )) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client,
                                    render_ui=lambda *args: self.fail("Color prose must not become a gallery"))
            result = await runtime.select(("Intro", "Interior material options include black leather.", "Caveat"), (call,))
        self.assertEqual(result, {})

    async def test_capability_instructions_prevent_live_dealer_promises(self):
        requests = []

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=complete({"sections": ["Open the local request form."]}))

        async def invoke(*args):
            self.fail("Booking capability response does not need a catalog tool")

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            await runtime.curate("Why do drivers care about wheelbase?", invoke)
        instructions = requests[0]["instructions"]
        for expected in (
            "no live dealership inventory connection",
            "contact a dealer, send calls or emails",
            "Never claim dealership availability or a confirmed appointment",
            "AI sales assistant",
            "Do not ask for contact details in chat",
            "mean unknown, never zero",
            "without being plugged in",
        ):
            self.assertIn(expected, instructions)

    async def test_named_comparison_retries_until_comparison_tool_succeeds(self):
        records = [
            {"model_id": "us-2027-cx5", "model_family": "cx5", "powertrain": "gasoline",
             "trims": [{"trim_id": "cx5-base-exact", "name": "2.5 S"}]},
            {"model_id": "us-2027-cx90-mhev", "model_family": "cx90", "powertrain": "mild_hybrid",
             "trims": [{"trim_id": "cx90-mhev-exact", "name": "Preferred"}]},
            {"model_id": "us-2027-cx90-phev", "model_family": "cx90", "powertrain": "plug_in_hybrid",
             "trims": [{"trim_id": "cx90-phev-exact", "name": "PHEV Preferred"}]},
        ]
        comparison = {
            "status": "completed",
            "output": [{"type": "function_call", "name": "compare_cars", "call_id": "compare-1",
                        "arguments": json.dumps({"trim_ids": ["cx5-base-exact", "cx90-phev-exact"]})}],
        }
        responses = [tool_response(), complete({"sections": ["Search-list comparison without the tool"]}),
                     comparison, complete({"sections": ["The grounded comparison."]})]
        requests = []
        invoked = []

        def transport(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=responses.pop(0))

        async def invoke(name, arguments, call_id):
            invoked.append((name, arguments))
            if name == "compare_cars":
                return {"records": [{"model_id": "us-2027-cx5"}, {"model_id": "us-2027-cx90-phev"}]}
            return {"records": deepcopy(records)}

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            sections = await runtime.curate("Compare CX-5 with CX-90 plug-in hybrid", invoke)
        self.assertEqual(sections, ["The grounded comparison."])
        self.assertEqual([name for name, _ in invoked], ["search_cars", "compare_cars"])
        correction = requests[2]["input"][-1]["content"]
        self.assertIn("successfully call compare_cars", correction)
        self.assertIn('"us-2027-cx90-phev"', correction)
        self.assertNotIn('"us-2027-cx90-mhev"', correction)

    async def test_ambiguous_comparison_can_ask_for_powertrain(self):
        raw = {"records": [
            {"model_id": "cx5", "model_family": "cx5", "powertrain": "gasoline", "trims": []},
            {"model_id": "mhev", "model_family": "cx90", "powertrain": "mild_hybrid", "trims": []},
            {"model_id": "phev", "model_family": "cx90", "powertrain": "plug_in_hybrid", "trims": []},
        ]}
        responses = [tool_response(), complete({"sections": ["Which CX-90 powertrain do you mean?"]})]

        async def invoke(*args):
            return deepcopy(raw)

        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=responses.pop(0))
        )) as client:
            runtime = OpenAIRuntime(ROOT, fast_catalog=False, api_key="fixture-only", client=client)
            sections = await runtime.curate("Compare CX-5 and CX-90", invoke)
        self.assertEqual(sections, ["Which CX-90 powertrain do you mean?"])
        self.assertEqual(responses, [])

    async def test_booking_uses_fresh_generation_with_explicit_capability_limits(self):
        requests = []
        calls = []

        def transport(request):
            payload = json.loads(request.content)
            requests.append(payload)
            if payload.get("tool_choice"):
                return httpx.Response(200, json={"status": "completed", "output": [{
                    "type": "function_call", "name": "get_test_drive_options",
                    "call_id": "call-booking", "arguments": "{}",
                }]})
            return httpx.Response(200, json=complete({"sections": ["Choose a preferred time."]}))

        async def invoke(*args):
            calls.append(args)
            return {}

        message = "Can I schedule a CX-5 test drive?"
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, api_key="fixture-only", client=client)
            for _ in range(2):
                self.assertEqual(await runtime.curate(message, invoke), ["Choose a preferred time."])
        self.assertEqual(calls, [("get_test_drive_options", {}, "call-booking")] * 2)
        self.assertEqual([request["input"] for request in requests], [message] * 4)
        self.assertIn("Never imply an appointment was arranged", requests[1]["instructions"])
        self.assertNotIn("save", requests[1]["instructions"])


    async def test_default_catalog_routes_grounded_sections_and_preserves_raw_handoff(self):
        from backend.catalog import Catalog
        from backend.ui_registry import UIRegistry
        catalog = Catalog(ROOT / "data/mazda/us/2027")
        def generate(request):
            facts = json.loads(json.loads(request.content)["input"])["grounded_sections"]
            return httpx.Response(200, json=complete({"sections": facts}))
        async with httpx.AsyncClient(transport=httpx.MockTransport(generate)) as client:
            runtime = OpenAIRuntime(ROOT, api_key="fixture", client=client, render_ui=UIRegistry(ROOT).render)
            for message, history, component in [
                ("Which of those is a plug-in hybrid?", ["Show Mazda SUVs under $60,000"], "CarList"),
                ("Tell me about 2027 CX-5 Preferred", [], "VehicleDetails"),
                ("Compare CX-5 with CX-90 plug-in hybrid", [], "CarComparison"),
                ("Show CX-5 interior photos and describe their luxurious leather", [], "VehicleGallery"),
                ("Show CX-5 colors", [], "ColorOptions"),
            ]:
                with self.subTest(message=message):
                    calls = []
                    async def invoke(name, arguments, call_id):
                        result = getattr(catalog, name)(**arguments)
                        calls.append(ToolResult(call_id, name, arguments, result))
                        return result
                    sections = await runtime.curate(message, invoke, history)
                    before = deepcopy(calls)
                    rendered = await runtime.select(tuple(sections), tuple(calls))
                    self.assertEqual(calls, before)
                    self.assertEqual(rendered[1]["component"], component)
                    self.assertEqual(rendered[1]["fallback_text"], sections[1])
                    if component == "CarList":
                        self.assertGreater(len(calls[0].result["records"]), 1)
                        self.assertEqual(len(rendered[1]["props"]["cars"]), 1)
                        self.assertIn("Plug-in", sections[1])
                    if component == "VehicleGallery":
                        self.assertNotIn("leather", " ".join(sections).casefold())
                        self.assertNotIn("luxurious", " ".join(sections).casefold())

    async def test_default_unknown_question_keeps_openai_reasoning(self):
        requests = []
        def transport(request):
            requests.append(request)
            return httpx.Response(200, json=complete({"sections": ["Please specify your needs."]}))
        async def invoke(*args):
            self.fail("Unexpected local tool")
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, api_key="fixture", client=client)
            result = await runtime.curate("Why do drivers care about wheelbase?", invoke)
        self.assertEqual(len(requests), 1)
        self.assertEqual(result, ["Please specify your needs."])

    async def test_shared_model_deadline_bounds_presentation(self):
        import asyncio
        from time import monotonic
        async def transport(request):
            await asyncio.sleep(1)
            self.fail("Request should have been cancelled")
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            runtime = OpenAIRuntime(ROOT, api_key="fixture", client=client)
            runtime._deadline.set(monotonic() + 0.01)
            with self.assertRaisesRegex(OpenAIRuntimeError, "timed out"):
                await runtime._request({})


    async def test_full_details_phev_keeps_catalog_handoff_with_live_generation(self):
        from backend.catalog import Catalog
        from backend.ui_registry import UIRegistry
        catalog = Catalog(ROOT / "data/mazda/us/2027")
        def generate(request):
            facts = json.loads(json.loads(request.content)["input"])["grounded_sections"]
            return httpx.Response(200, json=complete({"sections": facts}))
        async with httpx.AsyncClient(transport=httpx.MockTransport(generate)) as client:
            runtime = OpenAIRuntime(ROOT, api_key="fixture", client=client, render_ui=UIRegistry(ROOT).render)
            for modifier in ("full", "complete", "detailed"):
                calls = []
                async def invoke(name, arguments, call_id):
                    result = getattr(catalog, name)(**arguments)
                    calls.append(ToolResult(call_id, name, arguments, result))
                    return result
                sections = await runtime.curate(f"Show {modifier} details for CX-90 PHEV", invoke)
                ui = await runtime.select(tuple(sections), tuple(calls))
                self.assertEqual(ui[1]["component"], "VehicleDetails")
                self.assertEqual(calls[-1].name, "get_car_details")
                self.assertEqual(calls[-1].arguments["model_id"], "us-2027-cx90-phev")
                self.assertTrue(calls[-1].result["records"][0]["specifications"])

    async def test_detail_modifier_does_not_swallow_unhandled_question(self):
        from backend.openai_runtime import _catalog_request
        from backend.conversation import selection_for
        message = "Show full details for CX-90 PHEV and explain crashworthiness"
        self.assertFalse(_catalog_request(message, selection_for(message), []))
