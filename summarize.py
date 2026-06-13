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

Retourneer uitsluitend een geldig JSON-object met precies deze vier sleutels. Geen markdown, geen uitleg, geen codeblokken — alleen het JSON-object zelf.

Richtlijnen per sectie:

"ga4": 4–5 bullet points (•). Benoem de kernmetrics (sessies, gebruikers) met % verandering. \
Noem daarna de top pagina's bij naam (gebruik het paginapad) en highlight stijgers/dalers t.o.v. vorige week \
als die opvallend zijn (bijv. >20% verschil).

"gsc": 4–5 bullet points (•). Geef totaalcijfers (klikken, vertoningen, positie) met % verandering. \
Noem daarna 1–2 zoekwoorden die het meest zijn verbeterd in klikken of positie \
(gebruik de velden clicks_delta en position_delta uit de data — positieve position_delta = hogere ranking).

"ads": 4–5 bullet points (•), of null als er geen Ads-data is. Geef klikken, kosten en conversies met % verandering. \
Benoem het vertoningspercentage (search_impression_share_pct) als dat beschikbaar is, \
en of er impressies worden gemist door budget (lost_is_budget_pct) of ranking (lost_is_rank_pct).

"tips": 2–3 concrete, actionable tips gebaseerd op alle resultaten. Genummerd 1. 2. 3. \
Focus op de meest impactvolle acties die direct uitvoerbaar zijn.

DATA:
{data_json}"""

# Prefill forces Claude to begin the response with `{` — no preamble possible
_ASSISTANT_PREFILL = "{"


@dataclass
class ReportSections:
    ga4: str = ""
    gsc: str = ""
    ads: str | None = None
    tips: str = ""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ``` or ``` ... ```) if present."""
    text = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


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
        messages=[
            {"role": "user", "content": user_message},
            # Prefill: Claude will continue from this opening brace → guaranteed JSON start
            {"role": "assistant", "content": _ASSISTANT_PREFILL},
        ],
    )

    completion = next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )
    # Reconstruct the full JSON: prepend the prefill character we injected
    raw = _ASSISTANT_PREFILL + completion

    logger.debug(
        "Summary tokens: input=%d output=%d",
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    # Safety net: strip code fences in case the model ignored the prefill somehow
    raw = _strip_code_fences(raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Claude returned invalid JSON:\n%s", raw)
        return ReportSections(ga4=raw)

    return ReportSections(
        ga4=parsed.get("ga4", ""),
        gsc=parsed.get("gsc", ""),
        ads=parsed.get("ads"),
        tips=parsed.get("tips", ""),
    )
