"""Contextual MOBRA help with a Streamlit popover/expander compatibility path."""

from __future__ import annotations

from typing import Any

HELP_TOPICS: dict[str, str] = {
    "What is MOBRA?": "MOBRA is a prototype decision-support application for structured operational biosecurity readiness assessment in mobile biological laboratories.",
    "What does BRI mean?": "The BRI summarizes scored readiness requirements. It does not override deployment-blocking critical-control failures.",
    "Why can a high BRI still result in DO NOT DEPLOY?": "Deployment-blocking critical-control failures and configured validation or risk overrides take precedence over a high BRI.",
    "What is inherent risk?": "Inherent risk is calculated from the original Likelihood and Consequence values before residual controls are considered.",
    "What is residual risk?": "Residual risk is used only when a valid residual Likelihood and Consequence pair is supplied; missing residual data are never silently labelled residual risk.",
    "What is screening risk?": "Screening risk is an explicitly labelled inherent-risk substitute used when a residual assessment is missing. It is not a completed residual assessment.",
    "What do Heat Map numbers represent?": "The number shown inside a cell is the frequency of hazards with that Likelihood-Consequence combination. Cell colour communicates the risk category; the number is not a score.",
    "What is a deployment-blocking control?": "It is a provisional governance-profile control whose failed score, missing evidence, or incomplete record blocks an automatic deployment-ready result.",
    "What is a conditional gap?": "Conditional indicates that corrective action, ownership, target dates, formal approval, or compensating controls are required before acceptance.",
    "What is objective evidence?": "Objective evidence is a document, record, observation, or other traceable source that supports a requirement assessment; a narrative assertion alone may be insufficient.",
    "Why was a record excluded?": "Records with blocking validation errors remain visible for review but are excluded from calculations that require valid fields.",
    "What does software validation mean?": "Passing checks confirm software-rule consistency only; they do not establish scientific, clinical, operational, regulatory, institutional, or field validation.",
    "What is the difference between Refresh and Reset?": "Refresh View reruns the interface while preserving intended session data. Reset Assessment requires confirmation and clears application-owned assessment state.",
    "What information is included in email backup?": "Only the user-selected derived outputs are attached after explicit consent and authorization. Original uploads are excluded by default and SMTP secrets are never displayed.",
}


def help_topics() -> tuple[str, ...]:
    return tuple(HELP_TOPICS)


def render_help(topic: str, st_module: Any, *, expanded: bool = False) -> None:
    """Render a popover when supported, otherwise an equivalent expander."""
    content = HELP_TOPICS[topic]
    popover = getattr(st_module, "popover", None)
    if callable(popover):
        with popover(topic):
            st_module.write(content)
    else:
        with st_module.expander(topic, expanded=expanded):
            st_module.write(content)


def help_registered() -> bool:
    return len(HELP_TOPICS) >= 14 and all(label and text for label, text in HELP_TOPICS.items())


def fallback_help_available() -> bool:
    return bool(HELP_TOPICS)
