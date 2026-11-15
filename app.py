"""Vercel entrypoint for the hosted vehicle research app."""

from backend.main import create_app

app = create_app(test_drive_enabled=False)
