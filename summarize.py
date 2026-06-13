"""Generate a Dutch marketing summary via the Anthropic API."""
from __future__ import annotations

import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Je bent een senior digitaal marketeer die wekelijkse rapportages schrijft voor klanten. "
    "Schrijf uitsluitend in het Nederlands. "
    "Gebruik Slack mrkdwn-opmaak (vet met *tekst*, cursief met _tekst_, opsommingen met •). "
    "Wees bondig: maximaal 15 regels. "
    "Noem de belangrijkste stijgers en dalers met percentages. "
    "Toon is professioneel maar toegankelijk — geen jargon zonder uitleg."
)

_USER_TEMPLATE = """Schrijf een beknopte weeksamenvatting voor {client_name} (week {week_nr}).

Gebruik onderstaande data. Bereken zelf de procentuele veranderingen ten opzichte van de vorige periode.

{data_json}

Richtlijnen:
- Start direct met de samenvatting, geen inleiding.
- Benoem 2–4 opvallende ontwikkelingen met % verandering.
- Sluit af met één korte actie-aanbeveling.
- Maximaal 15 regels."""


def summarize(client_name: str, week_nr: int, data: dict[str, Any]) -> str:
    """Send data to Claude and return a Slack-formatted Dutch summary."""
    import json

    client = anthropic.Anthropic()
    user_message = _USER_TEMPLATE.format(
        client_name=client_name,
        week_nr=week_nr,
        data_json=json.dumps(data, ensure_ascii=False, indent=2),
    )

    logger.info("Requesting summary for %s (week %d)", client_name, week_nr)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    text = next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )
    logger.debug("Summary tokens: input=%d output=%d", response.usage.input_tokens, response.usage.output_tokens)
    return text
