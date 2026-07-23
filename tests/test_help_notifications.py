"""Tests for contextual-help registration and once-only notifications."""

from __future__ import annotations

from mobra.help_content import HELP_TOPICS, fallback_help_available, help_registered
from mobra.notifications import clear_notification_flags, notification_once


def test_help_topics_are_registered_and_have_fallback_content() -> None:
    assert help_registered()
    assert fallback_help_available()
    assert len(HELP_TOPICS) >= 14
    assert "What is MOBRA?" in HELP_TOPICS
    assert "What information is included in email backup?" in HELP_TOPICS
    assert all(label and text for label, text in HELP_TOPICS.items())


def test_notifications_do_not_repeat_on_rerun_and_reset_clears_flags() -> None:
    state: dict[str, object] = {}
    assert notification_once(state, "data_loaded", "loaded", level="success")
    assert not notification_once(state, "data_loaded", "loaded", level="success")
    assert notification_once(state, "analysis_completed", "analysis")
    clear_notification_flags(state)
    assert notification_once(state, "data_loaded", "loaded")
