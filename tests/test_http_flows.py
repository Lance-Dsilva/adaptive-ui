"""Exercise HTTP contracts using repository CSV fixtures."""

import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import load_settings


ROOT = Path(__file__).resolve().parents[1]


class HTTPFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(create_app()))

    def test_model_picker_returns_real_catalog_models(self):
        response = self.client.get("/catalog/models")
        self.assertEqual(response.status_code, 200)
        models = response.json()
        with (ROOT / "data/mazda/us/2027/models.csv").open(newline="", encoding="utf-8") as stream:
            expected = [
                {"id": row["model_id"], "name": row["name"], "year": int(row["model_year"])}
                for row in csv.DictReader(stream)
            ]
        self.assertEqual(models, expected)

    def test_all_catalog_actions_render_their_registered_components(self):
        actions = {
            "render_car_details": "VehicleDetails",
            "render_color_options": "ColorOptions",
            "render_vehicle_gallery": "VehicleGallery",
            "render_vehicle_visualization": "VehicleVisualization",
            "render_financing_offers": "FinancingOffers",
        }
        for tool, component in actions.items():
            with self.subTest(tool=tool):
                response = self.client.post("/catalog/presentation", json={
                    "tool_name": tool, "arguments": {"model_id": "us-2027-cx5"},
                })
                self.assertEqual(response.status_code, 200, response.text)
                blocks = response.json()["blocks"]
                expected_blocks = ["ui"] if tool == "render_car_details" else ["ui", "text"]
                self.assertEqual([block["type"] for block in blocks], expected_blocks)
                self.assertEqual(blocks[0]["component"], component)
                self.assertTrue(blocks[0]["code"])
                self.assertTrue(blocks[0]["fallback_text"])
                records = blocks[0]["props"]["records"]
                self.assertTrue(records)
                self.assertTrue(all(record["model_id"] == "us-2027-cx5" for record in records))
                if tool == "render_financing_offers":
                    self.assertTrue(all(record["expiry_status"] for record in records))
                    self.assertTrue(all(record["eligibility"] for record in records))
                elif tool != "render_car_details":
                    self.assertIn("assets", records[0])
                    self.assertIn("colors", records[0])
                    self.assertIn("visualizations", records[0])
                else:
                    self.assertTrue(records[0]["trims"])
                    self.assertTrue(records[0]["specifications"])

    def test_structured_catalog_actions_work_without_the_model(self):
        def perform(**request):
            response = self.client.post("/catalog/actions", json=request)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            return next(block for block in response.json()["blocks"] if block["type"] == "ui")

        with patch("httpx.AsyncClient.send", side_effect=AssertionError("No model call for UI actions")):
            picker = perform(intent="browse", filters={"body_style": "suv"}, compare=True, focus="engine specs")
            self.assertTrue(picker["props"]["startComparison"])
            self.assertEqual(picker["props"]["comparisonFocus"], "engine specs")
            cars = picker["props"]["cars"]
            self.assertEqual(len(cars), 3)
            hybrid = perform(intent="browse", filters={"body_style": "suv", "powertrain": "hybrid", "budget": 45000})
            self.assertEqual([car["id"] for car in hybrid["props"]["cars"]], ["us-2027-cx90-mhev"])
            selected = [cars[0]["configurations"][0], cars[1]["configurations"][0]]
            trims = [trim["trim_id"] for trim in selected]
            comparison = perform(intent="comparison", trim_ids=trims, focus="engine specs")
            self.assertEqual(comparison["props"]["question"], "engine specs")
            self.assertEqual([record["trim_id"] for record in comparison["props"]["records"]], trims)
            self.assertTrue(all(record["configuration_choices"] for record in comparison["props"]["records"]))
            spec = {"model_id": cars[0]["id"], "trim_id": trims[0]}
            for intent, component in (
                ("details", "VehicleDetails"), ("photos", "VehicleGallery"),
                ("rotation", "VehicleVisualization"), ("financing", "FinancingOffers"),
            ):
                self.assertEqual(perform(intent=intent, **spec)["component"], component)
            color = perform(intent="colors", **spec)["props"]["records"][0]["colors"][0]
            preview = perform(intent="color_preview", **spec, color_id=color["color_id"])
            self.assertEqual(preview["component"], "VehicleDetails")
            record = preview["props"]["records"][0]
            self.assertEqual(record["selected_color_id"], color["color_id"])
            self.assertEqual(record["selected_trim_id"], trims[0])
            self.assertEqual(perform(intent="test_drive")["component"], "TestDriveRequest")
            for request in (
                {"intent": "browse", "message": "show cars"},
                {"intent": "browse", "filters": {"budget": -1}},
                {"intent": "comparison", "trim_ids": [trims[0], trims[0]]},
                {"intent": "color_preview", "model_id": cars[0]["id"], "color_id": "bad"},
            ):
                self.assertEqual(self.client.post("/catalog/actions", json=request).status_code, 422)

    def test_catalog_actions_reject_unknown_tools_and_models(self):
        for payload in (
            {"tool_name": "render_unknown", "arguments": {"model_id": "us-2027-cx5"}},
            {"tool_name": "render_car_details", "arguments": {"model_id": "unknown"}},
            {"tool_name": "render_car_details", "arguments": {}},
            {"tool_name": "render_car_details", "arguments": {"model_id": "us-2027-cx5", "trim_id": "unknown"}},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/catalog/presentation", json=payload).status_code, 422)

    def test_capabilities_exposes_only_public_configuration(self):
        for key, configured in (("", False), ("test-secret-never-published", True)):
            with self.subTest(configured=configured), patch(
                "backend.main.load_settings",
                return_value={"OPENAI_API_KEY": key, "OPENAI_MODEL": "test-model"},
            ):
                response = self.client.get("/capabilities")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    "ai_configured": configured, "catalog_year": 2027, "test_drive_enabled": True,
                })
                self.assertNotIn("OPENAI", response.text)
                self.assertNotIn("test-secret", response.text)

    def test_hosted_model_setting_accepts_shell_style_quotes(self):
        for model in ('gpt-6-luna', '"gpt-6-luna"', " 'gpt-6-luna' ", '""'):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as root, patch.dict(
                "os.environ", {"OPENAI_API_KEY": "fixture-key", "OPENAI_MODEL": model}, clear=True,
            ):
                self.assertEqual(load_settings(Path(root)), {
                    "OPENAI_API_KEY": "fixture-key",
                    "OPENAI_MODEL": "gpt-6-luna",
                })

    def test_chat_rejects_invalid_messages_before_processing(self):
        with patch("backend.main.load_settings", side_effect=AssertionError("Invalid chat reached processing")):
            for message in ("", "x" * 2001):
                with self.subTest(length=len(message)):
                    self.assertEqual(self.client.post("/chat", json={"message": message}).status_code, 422)

    def test_hosted_test_drive_accepts_without_storing_or_echoing_input(self):
        from app import app

        future = (datetime.now(ZoneInfo("America/Chicago")) + timedelta(days=2)).date()
        payload = {
            "model_id": "us-2027-cx5", "requested_date": future.isoformat(), "requested_time": "12:30",
        }
        with TestClient(app) as client:
            self.assertTrue(client.get("/capabilities").json()["test_drive_enabled"])
            accepted = client.post("/test-drive-requests", json=payload)
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.json(), {"status": "demo_accepted"})
            self.assertEqual(accepted.headers["Cache-Control"], "no-store")
            for change in ({"model_id": "unknown"}, {"requested_date": "2000-01-01"}, {"requested_time": "invalid"}):
                with self.subTest(change=change):
                    self.assertEqual(client.post("/test-drive-requests", json=payload | change).status_code, 422)

    def test_financing_cards_include_starting_or_exact_trim_msrp(self):
        for trim_id, amount in ((None, "29990"), ("us-2027-cx5-2-5-s-select-suv-awd-6at-2r", "32140")):
            with self.subTest(trim=trim_id):
                arguments = {"model_id": "us-2027-cx5"}
                if trim_id:
                    arguments["trim_id"] = trim_id
                response = self.client.post("/catalog/presentation", json={
                    "tool_name": "render_financing_offers", "arguments": arguments,
                })
                self.assertEqual(response.status_code, 200, response.text)
                record = response.json()["blocks"][0]["props"]["records"][0]
                self.assertEqual(record["vehicle_price_usd"], amount)
