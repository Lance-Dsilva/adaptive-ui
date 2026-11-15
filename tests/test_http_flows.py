"""Exercise HTTP contracts using repository CSVs and isolated request storage."""

import csv
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
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
        for model in ('gpt-5-mini', '"gpt-5-mini"', " 'gpt-5-mini' ", '""'):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as root, patch.dict(
                "os.environ", {"OPENAI_API_KEY": "fixture-key", "OPENAI_MODEL": model}, clear=True,
            ):
                self.assertEqual(load_settings(Path(root)), {
                    "OPENAI_API_KEY": "fixture-key",
                    "OPENAI_MODEL": "gpt-5-mini",
                })

    def test_hosted_app_disables_local_test_drive_storage(self):
        from app import app

        with TestClient(app) as client, patch("backend.appointments.create_request") as save:
            self.assertFalse(client.get("/capabilities").json()["test_drive_enabled"])
            response = client.post("/test-drive-requests", json={
                "model_id": "us-2027-cx5", "requested_date": "2027-01-15",
                "requested_time": "15:00", "name": "Test Customer",
                "email": "test@example.invalid", "idempotency_key": "0c8a648c-81a1-4295-8c38-1f087408428d",
            })
            self.assertEqual(response.status_code, 503)
            save.assert_not_called()

    def test_chat_rejects_invalid_messages_before_processing(self):
        with patch("backend.main.load_settings", side_effect=AssertionError("Invalid chat reached processing")):
            for message in ("", "x" * 2001):
                with self.subTest(length=len(message)):
                    self.assertEqual(self.client.post("/chat", json={"message": message}).status_code, 422)

    def test_local_request_creation_retries_and_errors_are_isolated(self):
        with tempfile.TemporaryDirectory(prefix="adaptive-ui-http-") as directory:
            root = Path(directory)
            data = root / "data/mazda/us/2027"
            data.mkdir(parents=True)
            for filename in ("models.csv", "trims.csv"):
                shutil.copyfile(ROOT / "data/mazda/us/2027" / filename, data / filename)
            tomorrow = (datetime.now(ZoneInfo("America/Chicago")) + timedelta(days=2)).date().isoformat()
            payload = {
                "model_id": "us-2027-cx5",
                "requested_date": tomorrow,
                "requested_time": "12:30",
                "name": "HTTP Test Customer",
                "email": "http-test@example.invalid",
                "idempotency_key": str(uuid4()),
            }
            # Patch the destination only for appointment calls; registry fixtures remain real.
            with patch("backend.main.project_root", root):
                first = self.client.post("/test-drive-requests", json=payload)
                second = self.client.post("/test-drive-requests", json=payload)
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(second.status_code, 200, second.text)
                self.assertEqual(first.json(), second.json())
                self.assertEqual(first.json()["status"], "requested")
                self.assertEqual(first.json()["timezone"], "America/Chicago")
                self.assertEqual(first.json()["requested_time"], "12:30")
                self.assertNotIn("email", first.json())
                errors = [
                    payload | {"email": "different@example.invalid"},
                    payload | {"idempotency_key": str(uuid4()), "model_id": "unknown"},
                    payload | {"idempotency_key": str(uuid4()), "requested_date": "2000-01-01"},
                    payload | {"idempotency_key": str(uuid4()), "email": "invalid"},
                    payload | {"idempotency_key": "invalid-key"},
                ]
                for invalid in errors:
                    with self.subTest(payload=invalid):
                        self.assertEqual(self.client.post("/test-drive-requests", json=invalid).status_code, 422)

            with (root / "data/local/test_drive_requests.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["idempotency_key"], payload["idempotency_key"])
            self.assertEqual(rows[0]["request_id"], first.json()["request_id"])
