import csv
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from backend.appointments import create_request


ROOT = Path(__file__).resolve().parents[1]


class AppointmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        copytree(ROOT / "data/mazda/us/2027", self.root / "data/mazda/us/2027")
        tomorrow = datetime.now(ZoneInfo("America/Chicago")) + timedelta(days=1)
        self.payload = {
            "model_id": "us-2027-cx5", "requested_date": tomorrow.date().isoformat(),
            "requested_time": "14:30", "name": "Test Customer", "email": "test@example.com",
            "idempotency_key": "request-one",
        }

    def test_concurrent_retries_create_one_request(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: create_request(self.root, self.payload), range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(results[0]["status"], "requested")
        self.assertNotIn("email", results[0])
        with (self.root / "data/local/test_drive_requests.csv").open(newline="") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 1)

    def test_zero_seconds_normalize_for_retries(self):
        first = create_request(self.root, self.payload)
        second = create_request(self.root, self.payload | {"requested_time": "14:30:00"})
        self.assertEqual(first, second)

    def test_idempotency_key_conflict_rejected(self):
        create_request(self.root, self.payload)
        with self.assertRaises(ValueError):
            create_request(self.root, self.payload | {"requested_time": "15:00"})

    def test_invalid_and_past_dates_rejected(self):
        for change in (
            {"requested_date": "2000-01-01"}, {"requested_date": "2030-02-30"},
            {"requested_time": "25:00"}, {"requested_time": "14:30:01"},
            {"model_id": "unknown"}, {"email": "not-email"}, {"name": ""},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                create_request(self.root, self.payload | change)

    def test_failed_replace_keeps_original(self):
        from unittest.mock import patch
        result = create_request(self.root, self.payload)
        with patch("backend.appointments.os.replace", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                create_request(self.root, self.payload | {"idempotency_key": "two"})
        self.assertEqual(create_request(self.root, self.payload), result)
        self.assertEqual(len(list((self.root / "data/local").iterdir())), 2)
