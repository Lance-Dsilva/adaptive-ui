"""Persist local test-drive requests with idempotency and atomic CSV writes."""

import csv
import fcntl
import os
import re
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from .catalog import Catalog


_TIMEZONE = ZoneInfo("America/Chicago")
_INPUT_FIELDS = ("model_id", "requested_date", "requested_time", "name", "email", "idempotency_key")
_OUTPUT_FIELDS = ("request_id", "status", "model_id", "requested_date", "requested_time", "timezone")
_FIELDS = (*_OUTPUT_FIELDS, "name", "email", "idempotency_key")


def _validate(payload: dict) -> tuple[dict, datetime]:
    if not isinstance(payload, dict) or set(payload) != set(_INPUT_FIELDS):
        raise ValueError("Provide exactly the required test-drive request fields")
    if any(not isinstance(payload[field], str) for field in _INPUT_FIELDS):
        raise ValueError("Test-drive request fields must be strings")
    values = {key: payload[key].strip() for key in _INPUT_FIELDS}
    limits = {"model_id": 100, "name": 100, "email": 254, "idempotency_key": 128}
    for key, limit in limits.items():
        value = values[key]
        if not value or len(value) > limit or any(ord(character) < 32 for character in value):
            raise ValueError(f"Invalid {key}")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]):
        raise ValueError("Invalid email address")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values["requested_date"]):
        raise ValueError("Date must use YYYY-MM-DD")
    if re.fullmatch(r"\d{2}:\d{2}:00", values["requested_time"]):
        values["requested_time"] = values["requested_time"][:5]
    if not re.fullmatch(r"\d{2}:\d{2}", values["requested_time"]):
        raise ValueError("Time must use HH:MM")
    requested = datetime.combine(
        date.fromisoformat(values["requested_date"]),
        time.fromisoformat(values["requested_time"]),
        tzinfo=_TIMEZONE,
    )
    # Clock changes create absent or ambiguous local times. Ask for another time.
    utc_roundtrip = requested.astimezone(ZoneInfo("UTC")).astimezone(_TIMEZONE)
    if utc_roundtrip.replace(tzinfo=None) != requested.replace(tzinfo=None):
        raise ValueError("That local time does not exist because of a clock change")
    if requested.utcoffset() != requested.replace(fold=1).utcoffset():
        raise ValueError("That local time is ambiguous because of a clock change")
    return values, requested


def create_request(root: Path, payload: dict) -> dict:
    """Save a requested visit. Returning this record never confirms dealer availability."""
    values, requested = _validate(payload)
    catalog = Catalog(root / "data/mazda/us/2027")
    catalog._selection(values["model_id"])
    directory = root / "data/local"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "test_drive_requests.csv"
    lock_path = directory / "test_drive_requests.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = []
        if destination.exists():
            with destination.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != list(_FIELDS):
                    raise ValueError("The stored request file has an unsupported schema")
                rows = list(reader)
        for row in rows:
            if row["idempotency_key"] == values["idempotency_key"]:
                if any(row[key] != values[key] for key in _INPUT_FIELDS):
                    raise ValueError("The idempotency key belongs to a different request")
                return {key: row[key] for key in _OUTPUT_FIELDS}
        now = datetime.now(_TIMEZONE)
        if requested <= now:
            raise ValueError("Choose a future test-drive date and time")
        if (requested - now).days > 365:
            raise ValueError("Choose a date within the next year")
        row = {
            **values,
            "request_id": str(uuid4()),
            "status": "requested",
            "timezone": "America/Chicago",
        }
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=directory, delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                writer = csv.DictWriter(temporary, fieldnames=_FIELDS)
                writer.writeheader()
                writer.writerows([*rows, row])
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, destination)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return {key: row[key] for key in _OUTPUT_FIELDS}
