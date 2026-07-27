"""Reusable presentational components for MOBRA pages."""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import streamlit as st
import streamlit.components.v1 as components

from mobra.config import (
    APP_FULL_NAME,
    DECISION_COLORS,
    DECISION_ICONS,
    ICON_PATH,
    LOGO_DARK_PATH,
    LOGO_PATH,
    MUTED_TEXT_COLOR,
    PRIMARY_COLOR,
    RISK_COLORS,
    RISK_TEXT_COLORS,
)


MetricSpec = Mapping[str, str | int | float | None] | Sequence[str | int | float | None]


def scroll_to_top_html() -> str:
    """Return the isolated component script used after page navigation."""
    return """
    <script>
    (() => {
      const scrollToTop = () => {
        const parentWindow = window.parent;
        const parentDocument = window.parent.document;
        if (parentWindow.location.hash) {
          parentWindow.history.replaceState(
            null,
            "",
            `${parentWindow.location.pathname}${parentWindow.location.search}`
          );
        }
        const main = parentDocument.querySelector('[data-testid="stMain"]');
        const target = main || parentDocument.scrollingElement;
        if (target && typeof target.scrollTo === "function") {
          target.scrollTo({ top: 0, left: 0, behavior: "auto" });
        } else {
          parentWindow.scrollTo(0, 0);
        }
      };
      window.parent.requestAnimationFrame(() => scrollToTop());
      [100, 300, 750, 1500].forEach((delay) => {
        window.setTimeout(scrollToTop, delay);
      });
    })();
    </script>
    """


def render_scroll_to_top() -> None:
    """Scroll the Streamlit content pane to its beginning after navigation."""
    components.html(scroll_to_top_html(), height=0, scrolling=False)


@lru_cache(maxsize=1)
def _icon_data_uri() -> str:
    """Return the compact brand shield as an embeddable SVG data URI."""
    path = Path(ICON_PATH)
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


@lru_cache(maxsize=2)
def logo_data_uri(*, dark_background: bool = False) -> str:
    """Return the appropriate wordmark as an embeddable SVG data URI."""
    path = Path(LOGO_DARK_PATH if dark_background else LOGO_PATH)
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def render_logo(*, dark_background: bool = False, width: int = 300) -> None:
    """Render the appropriate transparent MOBRA wordmark with useful alt text."""
    uri = logo_data_uri(dark_background=dark_background)
    if uri:
        st.markdown(
            (
                f'<img src="{uri}" '
                f'alt="MOBRA — {escape(APP_FULL_NAME)} wordmark" '
                f'style="display:block;width:min(100%,{int(width)}px);height:auto">'
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown("## MOBRA")


def render_page_header(
    title: str,
    description: str,
    *,
    icon: str = "\u25c6",
    status: str | None = None,
) -> None:
    """Render a consistent page title, description, brand mark, and status."""
    status_html = (
        f'<span class="mobra-badge mobra-header-status">{escape(status)}</span>'
        if status
        else ""
    )
    icon_uri = _icon_data_uri()
    mark_html = (
        f'<img class="mobra-page-icon" src="{icon_uri}" alt="">'
        if icon_uri
        else f'<span class="mobra-page-icon mobra-page-icon-fallback">{escape(icon)}</span>'
    )
    st.markdown(
        f"""
        <div class="mobra-page-header">
          <div class="mobra-page-heading">
            {mark_html}
            <div><h1>{escape(title)}</h1><p>{escape(description)}</p></div>
          </div>
          <div>{status_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, *, icon: str | None = None, help_text: str | None = None) -> None:
    """Render a standardized section title and optional short explanation."""
    icon_html = f"<span>{escape(icon)}</span>" if icon else ""
    help_html = (
        f'<span class="mobra-help" title="{escape(help_text)}">\u24d8</span>'
        if help_text
        else ""
    )
    st.markdown(
        f'<div class="mobra-section">{icon_html}<h2>{escape(title)}</h2>{help_html}<span class="mobra-section-line"></span></div>',
        unsafe_allow_html=True,
    )


def metric_card_html(
    label: str,
    value: str | int | float,
    *,
    note: str = "",
    accent: str | None = None,
) -> str:
    """Build one KPI card as pure HTML for rendering and structure tests."""
    card_accent = accent or PRIMARY_COLOR
    note_html = escape(str(note)) if str(note) else "&nbsp;"
    return (
        f'<div class="mobra-metric-card" style="--metric-accent:{escape(card_accent)}">'
        f'<div class="mobra-metric-label">{escape(str(label))}</div>'
        f'<div class="mobra-metric-value">{escape(str(value))}</div>'
        f'<div class="mobra-metric-note">{note_html}</div>'
        "</div>"
    )


def _normalize_metric(metric: MetricSpec) -> tuple[str, str | int | float, str, str | None]:
    if isinstance(metric, Mapping):
        return (
            str(metric.get("label", "")),
            metric.get("value", ""),
            str(metric.get("note", "") or ""),
            str(metric["accent"]) if metric.get("accent") else None,
        )
    values = list(metric)
    if len(values) < 2:
        raise ValueError("Each metric requires at least a label and value.")
    values.extend(["", None])
    return str(values[0]), values[1], str(values[2] or ""), str(values[3]) if values[3] else None


def metric_grid_html(metrics: Iterable[MetricSpec], *, max_columns: int = 4) -> str:
    """Build a responsive KPI grid with 4/2/1-column CSS breakpoints."""
    columns = max(1, min(int(max_columns), 4))
    cards = []
    for metric in metrics:
        label, value, note, accent = _normalize_metric(metric)
        cards.append(metric_card_html(label, value, note=note, accent=accent))
    return (
        f'<div class="mobra-metric-grid" style="--metric-columns:{columns}">'
        + "".join(cards)
        + "</div>"
    )


def render_metric_grid(metrics: Iterable[MetricSpec], *, max_columns: int = 4) -> None:
    """Render KPI cards in a true responsive grid."""
    st.markdown(metric_grid_html(metrics, max_columns=max_columns), unsafe_allow_html=True)


def render_metric_card(
    label: str,
    value: str | int | float,
    *,
    note: str = "",
    accent: str | None = None,
) -> None:
    """Render a single KPI card; prefer ``render_metric_grid`` for card groups."""
    st.markdown(metric_card_html(label, value, note=note, accent=accent), unsafe_allow_html=True)


def render_status_badge(label: str, *, category: str | None = None) -> None:
    """Render a risk or operational status badge without relying on color alone."""
    key = category or label
    color = RISK_COLORS.get(key, PRIMARY_COLOR)
    text_color = RISK_TEXT_COLORS.get(key, "#FFFFFF")
    st.markdown(
        f'<span class="mobra-badge" style="background:{escape(color)};color:{escape(text_color)};border-color:{escape(color)}">\u25cf {escape(label)}</span>',
        unsafe_allow_html=True,
    )


def render_decision_banner(decision: str, reasons: Iterable[str] | None = None) -> None:
    """Render the deployment decision as the page's primary safety signal."""
    color = DECISION_COLORS.get(decision, PRIMARY_COLOR)
    icon = DECISION_ICONS.get(decision, "\u25c6")
    reasons_list = [str(reason) for reason in (reasons or []) if str(reason).strip()]
    explanation = reasons_list[0] if reasons_list else "Review the supporting evidence and required actions below."
    remaining = ""
    if len(reasons_list) > 1:
        remaining = "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in reasons_list[1:]) + "</ul>"
    st.markdown(
        f"""
        <div class="mobra-decision" style="--decision-color:{escape(color)}">
          <div class="mobra-decision-label">DEPLOYMENT DECISION</div>
          <h2>{escape(icon)}&nbsp; {escape(decision)}</h2>
          <p>{escape(explanation)}</p>{remaining}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(
    title: str = "No assessment data available",
    message: str = "Upload a supported file to begin the MOBRA readiness assessment.",
    *,
    icon: str = "\u25a6",
) -> None:
    """Render a clear non-technical empty state."""
    st.markdown(
        f"""
        <div class="mobra-empty">
          <div class="mobra-empty-icon">{escape(icon)}</div>
          <h3>{escape(title)}</h3><p>{escape(message)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_validation_alert(
    message: str,
    *,
    severity: str = "warning",
    details: str | None = None,
) -> None:
    """Render a validation message using clear user-facing language."""
    text = f"{message}\n\n{details}" if details else message
    renderer = {"error": st.error, "warning": st.warning, "info": st.info, "success": st.success}.get(severity, st.info)
    renderer(text)


def render_step(number: int, title: str, description: str) -> None:
    """Render one compact step in the data-import workflow."""
    st.markdown(
        f"""
        <div class="mobra-step">
          <span class="mobra-step-number">{number}</span>
          <div><strong>{escape(title)}</strong><br><span style="color:{MUTED_TEXT_COLOR}">{escape(description)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
