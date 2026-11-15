import asyncio
import csv
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from jsonschema.exceptions import ValidationError

from backend.main import create_app
from backend.orchestration import orchestrate
from backend.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[1]


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        settings = patch("backend.main.load_settings", return_value={"OPENAI_API_KEY": ""})
        settings.start()
        self.addCleanup(settings.stop)
        self.registry = ToolRegistry(ROOT)

    def test_catalog_filters_keep_original_values(self):
        search = {"model_year": 2027, "body_style": "hatchback", "drivetrain": "AWD"}
        result = self.registry.invoke("search_cars", search | {"max_msrp_usd": 29990})
        record, = result["records"]
        self.assertEqual(record["starting_msrp_usd"], "24750")
        self.assertEqual(record["matching_msrp_usd"], 29990)
        self.assertEqual(len(record["trims"]), 1)

        path = ROOT / "data" / "mazda" / "us" / "2027" / "assets.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            expected = next(row for row in csv.DictReader(stream) if row["asset_id"] == "asset-0541")
        self.assertIn("?thumbnail=1", expected["url"])
        # Family-only thumbnails with unverified depicted years stay in source CSV,
        # but cannot be attached without an explicit model/reference identity.
        self.assertNotIn(expected, record["assets"])
        for asset in record["assets"]:
            self.assertTrue(asset["model_id"] == record["model_id"]
                            or asset.get("reference_model_id") == record["model_id"])
        self.assertTrue(result["sources"])
        self.assertTrue(result["coverage"])
        self.assertFalse(
            self.registry.invoke("search_cars", search | {"max_msrp_usd": 29989})["records"]
        )

    def test_catalog_does_not_attach_other_powertrain_media(self):
        result = self.registry.invoke("search_cars", {"model_year": 2027, "model": "CX-90"})
        self.assertEqual(len(result["records"]), 2)
        for record in result["records"]:
            with self.subTest(model=record["model_id"]):
                for asset in record["assets"]:
                    self.assertIn(asset["model_id"], ("", record["model_id"]))
                    if asset.get("reference_model_id"):
                        self.assertEqual(asset["reference_model_id"], record["model_id"])
                        self.assertEqual(asset["applicability"], "model_reference")
                        self.assertEqual(asset["source_model_year"], "2026")
                        self.assertIn("2026", asset["caption"])
                    else:
                        self.assertEqual(asset["model_id"], record["model_id"])
                        self.assertEqual(asset["source_model_year"], "2027")

    def test_registry_rejects_invalid_inputs_and_disabled_tools(self):
        for arguments in ({}, {"model_year": True}, {"model_year": 2027, "city": "Austin"},
                          {"model_year": 2027, "max_msrp_usd": -1}):
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                self.registry.invoke("search_cars", arguments)
        with self.assertRaises(ValidationError):
            self.registry.invoke("compare_cars", {})

    def test_chat_returns_ordered_discovery_blocks(self):
        with TestClient(create_app(offline_catalog=True)) as client:
            response = client.post("/chat", json={"message": "Can you show me what cars are available for 2027?"})
            self.assertEqual(response.status_code, 200)
            *answer, effective, listing = response.json()["blocks"]
            self.assertEqual(effective["type"], "context")
            self.assertEqual(effective["items"], ["2027"])
            self.assertTrue(all(block["type"] == "text" for block in answer))
            self.assertEqual(listing["type"], "ui")
            self.assertEqual(listing["component"], "CarList")
            source = ROOT / "frontend" / "src" / "CarList.jsx"
            self.assertEqual(listing["code"], source.read_text(encoding="utf-8"))
            self.assertEqual(len(listing["fallback_text"].splitlines()), 4)
            self.assertFalse(any(block["text"] == listing["fallback_text"] for block in answer))
            self.assertIn("CX-5 — from $29,990.00", listing["fallback_text"])

            cars = {car["id"]: car for car in listing["props"]["cars"]}
            self.assertEqual(len(cars), 4)
            cx5 = cars["us-2027-cx5"]
            self.assertEqual(cx5["msrp"], 29990)
            raw = self.registry.invoke("search_cars", {"model_year": 2027, "model": "CX-5"})
            asset = next(asset for asset in raw["records"][0]["assets"] if asset["asset_id"] == "asset-0001")
            self.assertEqual(cx5["image_url"], asset["url"])
            self.assertEqual(cx5["trims"][0]["msrp"], 29990)
            phev = cars["us-2027-cx90-phev"]
            if phev["image_url"] is not None:
                self.assertTrue(phev["image_is_reference"])
                self.assertIn("2026 reference image; 2027 model may differ", phev["image_caption"])
                self.assertTrue(any(photo.get("reference_model_id") == phev["id"]
                                    and photo["url"] == phev["image_url"] for photo in phev["photos"]))
            self.assertEqual(client.post("/chat", json={"message": ""}).status_code, 422)
            empty = client.post("/chat", json={"message": "What cars are available in 2030?"})
            self.assertIn("no researched coverage", empty.json()["blocks"][0]["text"])

    def test_chat_suv_suggestions_filter_the_local_catalog(self):
        with TestClient(create_app(offline_catalog=True)) as client:
            for prompt in ("Show me Mazda SUVs.", "Show me 2027 Mazda SUVs."):
                with self.subTest(prompt=prompt):
                    response = client.post("/chat", json={"message": prompt})
                    self.assertEqual(response.status_code, 200)
                    listing = next(block for block in response.json()["blocks"] if block["type"] == "ui")
                    self.assertEqual(
                        [car["id"] for car in listing["props"]["cars"]],
                        ["us-2027-cx5", "us-2027-cx90-mhev", "us-2027-cx90-phev"],
                    )

    def test_fastapi_passes_complete_results_and_preserves_text(self):
        expected = self.registry.invoke("search_cars", {"model_year": 2027})

        async def curate(message, call_tool):
            first = await call_tool("search_cars", {"model_year": 2027}, "first")
            first["records"].clear()
            await call_tool("search_cars", {"model_year": 2026}, "second")
            return ["  Intro\n", "List fallback", "\nFollow-up  "]

        async def select(sections, calls):
            self.assertEqual([call.call_id for call in calls], ["first", "second"])
            self.assertEqual(calls[0].arguments, {"model_year": 2027})
            self.assertEqual(calls[0].result, expected)
            self.assertEqual(calls[1].result["records"], [])
            return {1: {
                "component": "CarList",
                "code": "test fixture",
                "props": {"cars": calls[0].result["records"]},
                "fallback_text": sections[1],
            }}

        with TestClient(create_app(curate, select)) as client:
            blocks = client.post("/chat", json={"message": "fixture"}).json()["blocks"]
        self.assertEqual(blocks[:3], [
            {"type": "text", "text": text} for text in ("  Intro\n", "List fallback", "\nFollow-up  ")
        ])
        self.assertEqual(blocks[3]["props"]["cars"], expected["records"])

    def test_presentation_failure_keeps_original_text(self):
        raw = {"nested": [{"url": "https://example.invalid/a?b=1&b=2", "null": None, "empty": []}]}

        async def invoke(name, arguments):
            return raw

        async def curate(message, call_tool):
            result = await call_tool("fixture", {}, "call-1")
            result["nested"][0]["empty"].append("changed")
            return ["before", "original", "after"]

        async def fail(sections, calls):
            self.assertEqual(calls[0].result, raw)
            raise RuntimeError("fixture failure")

        with self.assertLogs("backend.orchestration", level="WARNING"):
            response = asyncio.run(orchestrate("fixture", curate, fail, invoke))
        self.assertEqual(response["blocks"], [
            {"type": "text", "text": text} for text in ("before", "original", "after")
        ])
