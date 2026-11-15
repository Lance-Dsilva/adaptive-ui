"""Verify the test-drive demo validates its input without writing records."""

import shutil
import tempfile
import unittest
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.appointments import test_drive as accept_demo

ROOT = Path(__file__).resolve().parents[1]


class TestDriveDemoTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        data = self.root / "data/mazda/us/2027"
        data.mkdir(parents=True)
        for filename in ("models.csv", "trims.csv"):
            shutil.copyfile(ROOT / "data/mazda/us/2027" / filename, data / filename)
        self.future = datetime.now(ZoneInfo("America/Chicago")).date() + timedelta(days=2)

    def test_accepts_repeated_preferences_without_persistence(self):
        for _ in range(2):
            self.assertEqual(accept_demo(self.root, "us-2027-cx5", self.future, time(13)), {
                "status": "demo_accepted",
            })
        self.assertFalse((self.root / "data/local").exists())

    def test_rejects_unknown_vehicles_and_past_preferences(self):
        for model, day in (
            ("unknown", self.future),
            ("us-2027-cx5", self.future - timedelta(days=4)),
        ):
            with self.subTest(model=model, day=day), self.assertRaises(ValueError):
                accept_demo(self.root, model, day, time(13))
