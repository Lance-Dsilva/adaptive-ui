"""Validate a demo test-drive selection without recording it."""

from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from .catalog import Catalog

_TIMEZONE = ZoneInfo("America/Chicago")


def test_drive(root: Path, model_id: str, requested_date: date, requested_time: time) -> dict:
    Catalog(root / "data/mazda/us/2027")._selection(model_id)
    if requested_time.tzinfo is not None:
        raise ValueError("Choose a local time in America/Chicago")
    requested = datetime.combine(requested_date, requested_time, tzinfo=_TIMEZONE)
    roundtrip = requested.astimezone(ZoneInfo("UTC")).astimezone(_TIMEZONE)
    if roundtrip.replace(tzinfo=None) != requested.replace(tzinfo=None):
        raise ValueError("That local time does not exist because of a clock change")
    if requested.utcoffset() != requested.replace(fold=1).utcoffset():
        raise ValueError("That local time is ambiguous because of a clock change")
    now = datetime.now(_TIMEZONE)
    if requested <= now or (requested - now).days > 365:
        raise ValueError("Choose a future test-drive time within the next year")
    return {"status": "demo_accepted"}
