"""Weekly marketing report runner — iterates all clients in clients.yaml."""
from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

import ads
import ga4
import gsc
import slack
import summarize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "clients.yaml"


def _load_clients() -> list[dict[str, Any]]:
    with _CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)["clients"]


def _resolve_webhook(client_cfg: dict[str, Any]) -> str | None:
    """Return the webhook URL: client config takes priority, then env var."""
    return client_cfg.get("slack_webhook") or os.getenv("SLACK_WEBHOOK_URL")


def run_client(cfg: dict[str, Any]) -> None:
    name: str = cfg["name"]
    logger.info("=== Starting report for: %s ===", name)

    # Collect data
    ga4_data: dict[str, Any] | None = None
    gsc_data: dict[str, Any] | None = None
    ads_data: dict[str, Any] | None = None

    try:
        ga4_data = ga4.fetch(cfg["ga4_property_id"])
        logger.info("GA4 data collected for %s", name)
    except Exception:
        logger.exception("GA4 fetch failed for %s", name)

    try:
        gsc_data = gsc.fetch(cfg["gsc_site_url"])
        logger.info("GSC data collected for %s", name)
    except Exception:
        logger.exception("GSC fetch failed for %s", name)

    try:
        ads_data = ads.fetch(cfg.get("google_ads_customer_id", ""))
    except Exception:
        logger.exception("Ads fetch failed for %s", name)

    # Summarise
    week_nr = date.today().isocalendar()[1]
    combined: dict[str, Any] = {
        "ga4": ga4_data,
        "gsc": gsc_data,
        "google_ads": ads_data,
    }

    try:
        text = summarize.summarize(name, week_nr, combined)
    except Exception:
        logger.exception("Summarise failed for %s", name)
        return

    # Post to Slack
    webhook = _resolve_webhook(cfg)
    if not webhook:
        logger.warning("No Slack webhook configured for %s — skipping post", name)
        return

    try:
        slack.post(webhook, name, text)
    except Exception:
        logger.exception("Slack post failed for %s", name)


def main() -> None:
    clients = _load_clients()
    logger.info("Found %d client(s) in %s", len(clients), _CONFIG_PATH)

    errors: list[str] = []
    for cfg in clients:
        try:
            run_client(cfg)
        except Exception:
            name = cfg.get("name", "<unknown>")
            logger.exception("Unexpected error for client %s", name)
            errors.append(name)

    if errors:
        logger.error("Run completed with errors for: %s", ", ".join(errors))
        sys.exit(1)
    else:
        logger.info("All clients processed successfully.")


if __name__ == "__main__":
    main()
