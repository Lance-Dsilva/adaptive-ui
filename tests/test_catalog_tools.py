import csv
import unittest
from pathlib import Path

from backend.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[1]


class CatalogToolTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry(ROOT)
        with (ROOT / "data/mazda/us/2027/trims.csv").open(newline="") as stream:
            self.trims = list(csv.DictReader(stream))

    def test_details_reject_cross_model_trim(self):
        with self.assertRaises(ValueError):
            self.registry.invoke("get_car_details", {
                "model_id": "us-2027-cx5", "trim_id": self.trims[0]["trim_id"],
            })

    def test_unknown_model_rejected(self):
        for tool in ("get_car_details", "get_vehicle_media"):
            with self.subTest(tool=tool), self.assertRaises(ValueError):
                self.registry.invoke(tool, {"model_id": "missing"})

    def test_comparison_preserves_configuration_identity_and_order(self):
        trims = [row for row in self.trims if row["model_id"] == "us-2027-cx90-mhev"]
        pair = next(
            (a, b) for a in trims for b in trims
            if a["product_trim_code"] == b["product_trim_code"]
            and a["seating_rows"] != b["seating_rows"]
        )
        result = self.registry.invoke("compare_cars", {"trim_ids": [row["trim_id"] for row in pair]})
        for actual, original in zip(result["records"], pair):
            for key, value in original.items():
                self.assertEqual(actual[key], value)
        self.assertNotEqual(result["records"][0]["seating_rows"], result["records"][1]["seating_rows"])

    def test_media_preserves_raw_json_and_urls(self):
        trim = next(row for row in self.trims if row["model_id"] == "us-2027-cx5")
        result = self.registry.invoke("get_vehicle_media", {
            "model_id": trim["model_id"], "trim_id": trim["trim_id"], "color_code": "51K",
        })
        record = result["records"][0]
        for table in ("colors", "assets", "visualizations"):
            with (ROOT / f"data/mazda/us/2027/{table}.csv").open(newline="") as stream:
                originals = list(csv.DictReader(stream))
            self.assertTrue(record[table])
            for row in record[table]:
                self.assertIn(row, originals)
                self.assertEqual(row["color_code"], "51K")
                self.assertIn(row.get("product_trim_code"), ("", trim["product_trim_code"]))

    def test_expiration_boundary_and_missing_terms(self):
        arguments = {"model_id": "us-2027-cx5", "offer_type": "apr"}
        active = self.registry.invoke("get_financing_offers", arguments | {"as_of": "2026-11-30"})
        expired = self.registry.invoke("get_financing_offers", arguments | {"as_of": "2026-12-01"})
        self.assertEqual(active["records"][0]["expiry_status"], "within_recorded_expiry")
        self.assertEqual(expired["records"][0]["expiry_status"], "expired")
        for key in ("apr_percent", "eligibility", "geography", "source_url"):
            self.assertEqual(active["records"][0][key], expired["records"][0][key])
        missing = self.registry.invoke("get_financing_offers", {
            "model_id": "us-2027-cx90-phev", "offer_type": "apr", "as_of": "2026-11-13",
        })
        self.assertFalse(missing["records"])
        self.assertIn("unavailable", missing["warnings"][0])
