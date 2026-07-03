"""Validate Gmail email composition without making a network connection."""

from __future__ import annotations

import csv
from pathlib import Path

from send_daily_reports import ATTACHMENTS, RECIPIENT, SENDER, send_daily_reports


class FakeSMTP:
    instances = []

    def __init__(self) -> None:
        self.login_args = None
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def login(self, user: str, password: str):
        self.login_args = (user, password)

    def send_message(self, message):
        self.message = message


def main() -> int:
    delivery_log = Path("email_delivery_test.csv")
    delivery_log.unlink(missing_ok=True)
    FakeSMTP.instances.clear()
    try:
        result = send_daily_reports(
            password="test-app-password",
            delivery_log=delivery_log,
            smtp_factory=FakeSMTP,
        )
        assert result == "SENT"
        assert len(FakeSMTP.instances) == 1
        smtp = FakeSMTP.instances[0]
        assert smtp.login_args == (SENDER, "test-app-password")
        assert smtp.message["From"] == SENDER
        assert smtp.message["To"] == RECIPIENT
        filenames = sorted(
            part.get_filename()
            for part in smtp.message.iter_attachments()
        )
        assert filenames == sorted(path.name for path in ATTACHMENTS)
        assert all(filename.endswith(".md") for filename in filenames)
        assert not any(filename.endswith(".csv") for filename in filenames)
        assert not any(filename.endswith(".json") for filename in filenames)

        duplicate = send_daily_reports(
            password="test-app-password",
            delivery_log=delivery_log,
            smtp_factory=FakeSMTP,
        )
        assert duplicate == "SKIPPED_ALREADY_SENT"
        assert len(FakeSMTP.instances) == 1
        with delivery_log.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 1
        assert rows[0]["Status"] == "SENT"
        assert rows[0]["Attachments"].split(";") == [
            path.name for path in ATTACHMENTS
        ]
    finally:
        delivery_log.unlink(missing_ok=True)

    print("Daily Gmail report sender validation: PASS")
    print("Exactly four Markdown attachments: PASS")
    print("CSV/state/log exclusion: PASS")
    print("Duplicate-send protection: PASS")
    print("No network connection made during test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
