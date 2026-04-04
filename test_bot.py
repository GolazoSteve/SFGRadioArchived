import os
import tempfile
from datetime import datetime, timezone, timedelta
import pytest

# These imports will fail until run_bot.py exists — that's expected
from run_bot import is_archive_ready, already_posted, mark_as_posted


def test_archive_ready_when_4_5_hours_passed():
    game_start = datetime.now(timezone.utc) - timedelta(hours=5)
    assert is_archive_ready(game_start) is True


def test_archive_not_ready_when_only_3_hours_passed():
    game_start = datetime.now(timezone.utc) - timedelta(hours=3)
    assert is_archive_ready(game_start) is False


def test_archive_not_ready_exactly_at_4_5_hours():
    # Boundary: 1 second under 4.5 hours — not ready yet (strictly greater than)
    # Using exactly 4h30m would race against datetime.now() inside is_archive_ready
    game_start = datetime.now(timezone.utc) - timedelta(hours=4, minutes=29, seconds=59)
    assert is_archive_ready(game_start) is False


def test_already_posted_false_when_file_missing():
    assert already_posted(999999, "/nonexistent/path/posted_radio.txt") is False


def test_already_posted_false_when_gamepk_not_in_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("12345\n67890\n")
        path = f.name
    try:
        assert already_posted(99999, path) is False
    finally:
        os.unlink(path)


def test_already_posted_true_when_gamepk_present():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("12345\n67890\n")
        path = f.name
    try:
        assert already_posted(12345, path) is True
    finally:
        os.unlink(path)


def test_mark_as_posted_appends_gamepk():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("12345\n")
        path = f.name
    try:
        mark_as_posted(99999, path)
        with open(path) as f:
            lines = f.read().splitlines()
        assert "99999" in lines
        assert "12345" in lines  # original entry preserved
    finally:
        os.unlink(path)
