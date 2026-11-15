import unittest
from pathlib import Path

from backend.catalog import Catalog
from backend.conversation import curate, filter_records, selection_for


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.catalog = Catalog(Path(__file__).resolve().parents[1] / "data/mazda/us/2027")
        self.calls = []

    async def call_tool(self, name, arguments, call_id):
        self.calls.append((name, arguments, call_id))
        return getattr(self.catalog, name)(**arguments)

    async def test_budget_paraphrase(self):
        sections = await curate("Can I see Mazda SUVs under $35,000?", self.call_tool)
        self.assertIn("CX-5", sections[1])
        self.assertNotIn("CX-90", sections[1])
        self.assertEqual(self.calls[0][1]["max_msrp_usd"], 35000)

    async def test_followup_preserves_budget_and_distinguishes_phev(self):
        history = ["Show me Mazda SUVs under $60,000"]
        message = "Which of those is a plug-in hybrid?"
        sections = await curate(message, self.call_tool, history)
        self.assertIn("Plug-in Hybrid", sections[1])
        self.assertNotIn("Inline 6", sections[1])
        selection = selection_for(message, history)
        self.assertEqual(selection.budget, 60000)
        raw = self.catalog.search_cars(2027)
        selected = filter_records(raw["records"], selection)
        self.assertEqual(len(selected), 1)
        self.assertIs(selected[0], raw["records"][-1])

    async def test_named_comparison(self):
        sections = await curate("Compare the CX-5 and CX-90 plug-in", self.call_tool)
        self.assertIn("CX-5", sections[1])
        self.assertIn("CX-90", sections[1])
        self.assertNotIn("Mazda3", sections[1])

    async def test_year_coverage_and_booking_recovery(self):
        sections = await curate("What Mazda vehicles are available for 2026?", self.call_tool)
        self.assertIn("no researched coverage for 2026", sections[0])
        self.assertFalse(self.calls)
        booking = await curate("Book a test drive", self.call_tool)
        self.assertIn("does not save your details", booking[0])

    async def test_details_and_new_query_reset(self):
        sections = await curate("What can you tell me about the CX-5?", self.call_tool)
        self.assertIn("AWD", sections[1])
        selection = selection_for("Show me Mazda3 hatchbacks", ["Show me Mazda SUVs under $35000"])
        self.assertEqual(selection.models, ["mazda3"])
        self.assertIsNone(selection.budget)
        self.assertEqual(selection.body_style, "hatchback")

    async def test_non_plugin_hybrid_and_qualified_comparison(self):
        sections = await curate("Show me hybrids that don’t need to be plugged in", self.call_tool)
        self.assertIn("Inline 6 Turbo", sections[1])
        self.assertNotIn("Plug-in Hybrid", sections[1])
        sections = await curate("Compare CX-5 to CX-90 plug-in", self.call_tool)
        self.assertIn("CX-5", sections[1])
        self.assertIn("Plug-in Hybrid", sections[1])
        self.assertEqual(self.calls[-1][0], "compare_cars")
        sections = await curate("Compare CX-5 and CX-90", self.call_tool)
        self.assertIn("should I compare", sections[0])

    async def test_media_modes_use_actual_tools(self):
        for message, mode in (
            ("Show CX-5 colors", "colors"),
            ("Show Soul Red for CX-5", "colors"),
            ("Show photos of CX-5", "gallery"),
            ("Show CX-5 in 3D", "visualization"),
        ):
            with self.subTest(message=message):
                sections = await curate(message, self.call_tool)
                self.assertEqual(len(sections), 3)
                self.assertEqual(self.calls[-1][0], "get_vehicle_media")
                self.assertEqual(selection_for(message).mode, mode)
        self.assertIn("Soul Red", (await curate("Show Soul Red for CX-5", self.call_tool))[1])

    async def test_preferred_details_destination_and_finance_followup(self):
        sections = await curate("Tell me about CX-5 Preferred", self.call_tool)
        self.assertEqual(self.calls[-1][0], "get_car_details")
        self.assertIn("preferred", self.calls[-1][1]["trim_id"])
        self.assertIn("destination", sections[1])
        sections = await curate("MSRP plus destination for CX-5", self.call_tool)
        self.assertIn("subtotal", sections[1])
        sections = await curate("What about a down payment?", self.call_tool, ["Tell me about CX-5"])
        self.assertEqual(self.calls[-1][0], "get_financing_offers")
        self.assertIn("as_of", self.calls[-1][1])
        self.assertIn("expiry", sections[1])

    async def test_missing_model_and_booking_action(self):
        missing = await curate("Show CX-50 colors", self.call_tool)
        self.assertIn("snapshot covers Mazda3, CX-5, and CX-90", missing[0])
        booking = await curate("Schedule a test drive", self.call_tool)
        self.assertIn("Chat options, then Request test drive", booking[0])
        self.assertIn("or book an appointment", booking[0])

    async def test_followup_after_new_search_drops_stale_budget_and_model(self):
        selection = selection_for("Which of those is a plug-in hybrid?", [
            "Show CX-5 under $35000", "Show me Mazda SUVs",
        ])
        self.assertIsNone(selection.budget)
        self.assertEqual(selection.models, [])
        self.assertEqual(selection.powertrain, "plug_in_hybrid")
        sections = await curate("Which of those is a plug-in hybrid?", self.call_tool,
                                ["Show CX-5 under $35000", "Show me Mazda SUVs"])
        self.assertIn("Plug-in Hybrid", sections[1])
        self.assertNotIn("CX-5", sections[1])

    async def test_gallery_fallback_does_not_describe_filename_appearance(self):
        sections = await curate("Show photos of CX-5", self.call_tool)
        self.assertNotIn("leather", " ".join(sections).lower())
        self.assertNotIn("front", sections[1].lower())
        self.assertNotIn(".jpg", sections[1])
