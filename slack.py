"""Post a report to Slack via a webhook using Block Kit."""
from __future__ import annotations

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)


def post(webhook_url: str, client_name: str, summary: str) -> None:
    """Post the weekly summary to Slack with a Block Kit header."""
    week_nr = date.today().isocalendar()[1]
    year = date.today().year

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 {client_name} — Week {week_nr}, {year}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary,
                },
            },
        ]
    }

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()
    logger.info("Slack message posted for %s (week %d)", client_name, week_nr)
