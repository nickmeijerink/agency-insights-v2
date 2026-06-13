"""Generate structured Dutch marketing summaries via the Anthropic API."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Je bent een enthousiaste maar professionele digitale marketeer die wekelijkse performance-updates "
    "schrijft. Schrijf uitsluitend in het Nederlands. "
    "Gebruik Slack mrkdwn-opmaak: *vet* voor nadruk, _cursief_ optioneel, opsommingen met •. "
    "Wees beknopt en concreet. Bereken altijd zelf de procentuele veranderingen ten opzichte van "
    "de vorige periode. Noem concrete cijfers en percentages. Geen jargon zonder uitleg."
)

_USER_TEMPLATE = """Analyseer de onderstaande marketingdata voor {client_name} (week {week_nr}) en lever een JSON-object terug met precies de volgende sleutels:

- "ga4": korte samenvatting van de Google Analytics 4 opvallendheden (max 4 regels, Slack mrkdwn, bullet points met •)
- "gsc": korte samenvatting van de Search Console opvallendheden (max 4 regels, Slack mrkdwn, bullet points met •)
- "ads": korte samenvatting van de Google Ads opvallendheden (max 4 regels, Slack mrkdwn, bullet points met •), of null als er geen Ads-data is
- "tips": 2 à 3 concrete, actionable tips voor deze week gebaseerd op alle resultaten samen (max 4 regels, Slack mrkdwn, genummerd met 1. 2. 3.)

Lever ALLEEN het JSON-object terug, zonder markdown-codeblokken of extra tekst.

DATA:
{data_json}"""


@dataclass
class ReportSections:
    ga4: str = ""
    gsc: str = ""
    ads: str | None = None
    tips: str = ""


def summarize(client_name: str, week_nr: int, data: dict[str, Any]) -> ReportSections:
    """Ask Claude for per-source summaries and tips; return a ReportSections dataclass."""
    client = anthropic.Anthropic()
    user_message = _USER_TEMPLATE.format(
        client_name=client_name,
        week_nr=week_nr,
        data_json=json.dumps(data, ensure_ascii=False, indent=2),
    )

    logger.info("Requesting structured summary for %s (week %d)", client_name, week_nr)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = next(
        (block.text for block in response.content if block.type == "text"),
        "{}",
    )
    logger.debug(
        "Summary tokens: input=%d output=%d",
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Claude returned invalid JSON:\n%s", raw)
        # Graceful fallback: put everything in GA4 field so something is posted
        return ReportSections(ga4=raw)

    return ReportSections(
        ga4=parsed.get("ga4", ""),
        gsc=parsed.get("gsc", ""),
        ads=parsed.get("ads"),  # None when ads data was absent
        tips=parsed.get("tips", ""),
    )
