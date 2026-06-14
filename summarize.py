"""Generate structured Dutch marketing summaries via the Anthropic API."""
from __future__ import annotations

import json
import logging
import re
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

_USER_TEMPLATE = """Analyseer de onderstaande marketingdata voor {client_name} (week {week_nr}).

Retourneer UITSLUITEND een geldig JSON-object — geen inleiding, geen uitleg, geen markdown, \
geen codeblokken. Start direct met {{ en eindig met }}.

Gebruik precies deze vier sleutels:

"ga4": 4–5 bullet points (•). Benoem de kernmetrics (sessies, gebruikers) met % verandering. \
Noem daarna de top pagina's bij naam (gebruik het paginapad) en highlight stijgers/dalers t.o.v. \
vorige week als die opvallend zijn (bijv. >20% verschil).

"gsc": 4–5 bullet points (•). Geef totaalcijfers (klikken, vertoningen, positie) met % verandering. \
Noem daarna 1–2 zoekwoorden die het meest zijn verbeterd in klikken of positie \
(positieve position_delta = hogere ranking).

"ads": 4–5 bullet points (•), of null als er geen Ads-data is. Geef klikken, kosten en conversies \
met % verandering. Benoem het vertoningspercentage (search_impression_share_pct) als beschikbaar, \
en of impressies worden gemist door budget (lost_is_budget_pct) of ranking (lost_is_rank_pct).

"tips": 2–3 concrete, actionable tips gebaseerd op alle resultaten. Genummerd 1. 2. 3.

DATA:
{data_json}"""


@dataclass
class ReportSections:
    ga4: str = ""
    gsc: str = ""
    ads: str | None = None
    tips: str = ""


def _extract_json(text: str) -> str:
    """Extract the first complete JSON object from text, stripping any surrounding content."""
    text = text.strip()

    # Strip markdown code fences if present
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Find the first { and match its closing }
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # No balanced JSON found — return from first { to end as best effort
    return text[start:]


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
        max_tokens=1600,
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

    candidate = _extract_json(raw)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        logger.error("Claude returned invalid JSON:\n%s", raw)
        return ReportSections(ga4=raw)

    return ReportSections(
        ga4=parsed.get("ga4", ""),
        gsc=parsed.get("gsc", ""),
        ads=parsed.get("ads"),
        tips=parsed.get("tips", ""),
    )
