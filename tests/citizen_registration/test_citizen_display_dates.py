"""Client display-date parsing tests."""

import pytest

from client.display_dates import format_display_date, parse_display_date


def test_display_date_requires_timezone_and_converts_to_bogota() -> None:
    value = parse_display_date("2026-11-14T20:00:00+00:00")
    assert value.isoformat() == "2026-11-14T15:00:00-05:00"
    assert format_display_date("2026-11-14T20:00:00Z") == "14/11/2026 15:00"
    with pytest.raises(ValueError):
        parse_display_date("2026-11-14T20:00:00")
