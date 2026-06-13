"""Google Ads data fetcher (stub — full implementation pending)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def fetch(customer_id: str) -> dict[str, Any] | None:
    """Fetch Google Ads data for the given customer.

    Returns None when customer_id is empty (client has no Ads account).
    Full implementation can be added once the google-ads library is configured.
    """
    if not customer_id:
        logger.debug("No Google Ads customer_id configured, skipping.")
        return None

    logger.warning("Google Ads fetch not yet implemented for customer %s", customer_id)
    return None
