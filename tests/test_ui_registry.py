import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copyfile

from backend.orchestration import ToolResult
from backend.registry import ToolRegistry
from backend.ui_registry import UIRegistry


ROOT = Path(__file__).resolve().parents[1]


class UIRegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / "registries").mkdir()
        (root / "frontend/src").mkdir(parents=True)
        copyfile(ROOT / "registries/ui_tools.yaml", root / "registries/ui_tools.yaml")
        (root / "frontend/src/VehicleExperience.jsx").write_text("trusted React fixture")
        (root / "frontend/src/CarList.jsx").write_text("trusted list fixture")
        self.ui = UIRegistry(root)
        self.domain = ToolRegistry(ROOT)

    def test_exact_records_and_fallback_survive_selection(self):
        result = self.domain.invoke("get_car_details", {"model_id": "us-2027-cx5"})
        call = ToolResult("source", "get_car_details", {"model_id": "us-2027-cx5"}, result)
        block = self.ui.render("render_car_details", call, [0], "  Original\ntext ")
        self.assertEqual(block["component"], "VehicleDetails")
        self.assertEqual(block["code"], "trusted React fixture")
        self.assertEqual(block["fallback_text"], "  Original\ntext ")
        self.assertEqual(block["props"]["records"], result["records"])
        block["props"]["records"][0]["assets"].clear()
        self.assertTrue(result["records"][0]["assets"])

    def test_invalid_indices_and_source_tools_rejected(self):
        call = ToolResult("source", "get_vehicle_media", {}, {"records": [{"assets": []}]})
        for indices in ([-1], [1], [0, 0], [True], ["0"], None):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                self.ui.render("render_vehicle_gallery", call, indices, "fallback")
        with self.assertRaises(ValueError):
            self.ui.render("render_financing_offers", call, [0], "fallback")

    def test_car_list_uses_source_image_and_price(self):
        result = self.domain.invoke("search_cars", {"model_year": 2027, "model": "CX-5"})
        call = ToolResult("source", "search_cars", {}, result)
        block = self.ui.render("render_car_list", call, [0], "fallback")
        car = block["props"]["cars"][0]
        self.assertEqual(car["msrp"], result["records"][0]["matching_msrp_usd"])
        self.assertIn(car["image_url"], [row["url"] for row in result["records"][0]["assets"]])

    def test_comparison_preserves_requested_order(self):
        rows = [{"trim_id": "b", "nested": {"url": "https://example.invalid/?a=1&a=2"}},
                {"trim_id": "a", "empty": None}]
        call = ToolResult("source", "compare_cars", {}, {"records": rows})
        block = self.ui.render("render_car_comparison", call, [1, 0], "fallback")
        self.assertEqual(block["component"], "CarComparison")
        self.assertEqual(block["props"]["records"], [rows[1], rows[0]])
