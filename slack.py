"""Post a structured weekly report to Slack via Block Kit."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import requests

from summarize import ReportSections

logger = logging.getLogger(__name__)

_OPENING = (
    "Hoi toppers, Maik de razende reporter is hier! 😎\n\n"
    "Ik stuur wekelijks een performance update over jullie eigen website!"
)

_CLOSING = "Succes deze week en tot volgende week! 👋"


def _section(text: str) -> dict:
    """Shorthand for a mrkdwn section block."""
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


_MAANDEN = [
    "", "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def _format_date(d: date) -> str:
    return f"{d.day} {_MAANDEN[d.month]}"


def post(webhook_url: str, client_name: str, sections: ReportSections) -> None:
    """Build a Block Kit payload and POST it to the Slack webhook."""
    today = date.today()
    week_nr = today.isocalendar()[1]
    year = today.year

    # Current period: yesterday-6 → yesterday (matches ga4.py / gsc.py)
    curr_end = today - timedelta(days=1)
    curr_start = today - timedelta(days=7)
    prev_end = today - timedelta(days=8)
    prev_start = today - timedelta(days=14)

    period_line = (
        f"_Periode: *{_format_date(curr_start)} – {_format_date(curr_end)}* "
        f"vergeleken met {_format_date(prev_start)} – {_format_date(prev_end)}._"
    )

    blocks: list[dict] = [
        # ── Header ──────────────────────────────────────────────────────────
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{client_name} — Week {week_nr}, {year}",
                "emoji": True,
            },
        },
        {"type": "divider"},
        # ── Vaste opening ───────────────────────────────────────────────────
        _section(_OPENING),
        _section(period_line),
        {"type": "divider"},
    ]

    # ── GA4 (altijd aanwezig) ────────────────────────────────────────────────
    if sections.ga4:
        blocks += [
            _section("*📊 Google Analytics 4*"),
            _section(sections.ga4),
            {"type": "divider"},
        ]

    # ── GSC (alleen als er data is) ──────────────────────────────────────────
    if sections.gsc:
        blocks += [
            _section("*🔍 Google Search Console*"),
            _section(sections.gsc),
            {"type": "divider"},
        ]

    # ── Google Ads (optioneel) ───────────────────────────────────────────────
    if sections.ads:
        blocks += [
            _section("*📣 Google Ads*"),
            _section(sections.ads),
            {"type": "divider"},
        ]

    # ── Tips ────────────────────────────────────────────────────────────────
    if sections.tips:
        blocks += [
            _section("*💡 Tips voor deze week*"),
            _section(sections.tips),
            {"type": "divider"},
        ]

    # Afsluiting zonder trailing divider
    blocks += [
        # ── Vaste afsluiting ────────────────────────────────────────────────
        _section(_CLOSING),
    ]

    payload = {"blocks": blocks}
    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()
    logger.info("Slack message posted for %s (week %d)", client_name, week_nr)
