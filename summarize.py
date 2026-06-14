"""Generate structured Dutch marketing summaries via the Anthropic API."""
from __future__ import annotations

import logging
from dataclasses import dataclass
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

_USER_TEMPLATE = """Analyseer de onderstaande marketingdata voor {client_name} (week {week_nr}) \
en roep de tool `save_report_sections` aan met de samenvatting per kanaal.

Richtlijnen per sectie:

ga4: 4–5 bullet points (•). Benoem de kernmetrics (sessies, gebruikers) met % verandering. \
Noem daarna de top pagina's bij naam (paginapad) en highlight stijgers/dalers t.o.v. vorige week \
als die opvallend zijn (bijv. >20% verschil).

gsc: 4–5 bullet points (•). Geef totaalcijfers (klikken, vertoningen, positie) met % verandering. \
Noem 1–2 zoekwoorden die het meest verbeterd zijn in klikken of positie \
(positieve position_delta = hogere ranking).

ads: 4–5 bullet points (•), of laat leeg als er geen Ads-data is. Geef klikken, kosten en \
conversies met % verandering. Benoem het vertoningspercentage (search_impression_share_pct) \
als beschikbaar, en verloren impressies door budget of ranking.

tips: 2–3 concrete, actionable tips gebaseerd op alle resultaten. Genummerd 1. 2. 3.

DATA:
{data_json}"""

# Tool definition — Claude must call this; schema enforces the structure
_TOOL = {
    "name": "save_report_sections",
    "description": "Sla de wekelijkse marketingsamenvatting op per kanaal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ga4": {
                "type": "string",
                "description": "Samenvatting Google Analytics 4, Slack mrkdwn met bullet points (•).",
            },
            "gsc": {
                "type": "string",
                "description": "Samenvatting Google Search Console, Slack mrkdwn met bullet points (•).",
            },
            "ads": {
                "type": ["string", "null"],
                "description": "Samenvatting Google Ads, Slack mrkdwn met bullet points (•). Null als er geen Ads-data is.",
            },
            "tips": {
                "type": "string",
                "description": "2–3 concrete tips, genummerd 1. 2. 3., Slack mrkdwn.",
            },
        },
        "required": ["ga4", "gsc", "ads", "tips"],
    },
}


@dataclass
class ReportSections:
    ga4: str = ""
    gsc: str = ""
    ads: str | None = None
    tips: str = ""


def summarize(client_name: str, week_nr: int, data: dict[str, Any]) -> ReportSections:
    """Ask Claude for per-source summaries using tool use; return a ReportSections dataclass."""
    import json

    client = anthropic.Anthropic()
    user_message = _USER_TEMPLATE.format(
        client_name=client_name,
        week_nr=week_nr,
        data_json=json.dumps(data, ensure_ascii=False, indent=2),
    )

    logger.info("Requesting structured summary for %s (week %d)", client_name, week_nr)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1600,
        system=_SYSTEM,
        tools=[_TOOL],
        # Force Claude to call exactly this tool — plain text is not an option
        tool_choice={"type": "tool", "name": "save_report_sections"},
        messages=[{"role": "user", "content": user_message}],
    )

    logger.debug(
        "Summary tokens: input=%d output=%d",
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    # Extract the tool_use block — guaranteed to be present due to tool_choice
    tool_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_block is None:
        logger.error("No tool_use block in response: %s", response.content)
        return ReportSections(ga4="(samenvatting niet beschikbaar)")

    args = tool_block.input  # already a dict, no JSON parsing needed
    return ReportSections(
        ga4=args.get("ga4", ""),
        gsc=args.get("gsc", ""),
        ads=args.get("ads"),
        tips=args.get("tips", ""),
    )
