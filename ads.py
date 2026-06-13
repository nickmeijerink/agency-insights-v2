"""Google Ads data fetcher via the Google Ads API."""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def _date_range(offset_start: int, offset_end: int) -> tuple[str, str]:
    today = date.today()
    start = (today - timedelta(days=offset_start)).isoformat()
    end = (today - timedelta(days=offset_end)).isoformat()
    return start, end


def _get_client() -> Any:
    """Build a GoogleAdsClient from environment variables."""
    from google.ads.googleads.client import GoogleAdsClient  # noqa: PLC0415

    config = {
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)


def _clean_customer_id(customer_id: str) -> str:
    """Strip dashes so '698-868-8484' becomes '6988688484'."""
    return customer_id.replace("-", "")


def _run_summary(client: Any, customer_id: str, start: str, end: str) -> dict[str, float]:
    """Fetch account-level totals for the given date range."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            metrics.clicks,
            metrics.impressions,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM customer
        WHERE segments.date BETWEEN '{start}' AND '{end}'
    """

    response = ga_service.search(customer_id=customer_id, query=query)

    clicks = impressions = cost_micros = conversions = ctr_sum = avcpc_sum = 0.0
    rows = 0
    for row in response:
        m = row.metrics
        clicks += m.clicks
        impressions += m.impressions
        cost_micros += m.cost_micros
        conversions += m.conversions
        ctr_sum += m.ctr
        avcpc_sum += m.average_cpc
        rows += 1

    return {
        "clicks": int(clicks),
        "impressions": int(impressions),
        "cost_eur": round(cost_micros / 1_000_000, 2),
        "conversions": round(conversions, 1),
        "ctr_pct": round((ctr_sum / rows * 100) if rows else 0.0, 2),
        "avg_cpc_eur": round((avcpc_sum / rows / 1_000_000) if rows else 0.0, 2),
    }


def _run_top_campaigns(
    client: Any, customer_id: str, start: str, end: str
) -> list[dict[str, Any]]:
    """Fetch top 5 campaigns by spend for the given date range."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.name,
            metrics.clicks,
            metrics.impressions,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{start}' AND '{end}'
            AND campaign.status != 'REMOVED'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 5
    """

    response = ga_service.search(customer_id=customer_id, query=query)

    campaigns = []
    for row in response:
        m = row.metrics
        campaigns.append(
            {
                "name": row.campaign.name,
                "clicks": int(m.clicks),
                "impressions": int(m.impressions),
                "cost_eur": round(m.cost_micros / 1_000_000, 2),
                "conversions": round(m.conversions, 1),
            }
        )
    return campaigns


def fetch(customer_id: str) -> dict[str, Any] | None:
    """Fetch Google Ads data for the last 7 days vs the 7 days before that.

    Returns None when customer_id is empty or required env vars are missing.
    """
    if not customer_id:
        logger.debug("No Google Ads customer_id configured, skipping.")
        return None

    required = [
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET",
        "GOOGLE_ADS_REFRESH_TOKEN",
    ]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.warning("Google Ads env vars not set (%s), skipping.", ", ".join(missing))
        return None

    cid = _clean_customer_id(customer_id)

    # Current period: 7 days ago → yesterday
    curr_start, curr_end = _date_range(7, 1)
    # Previous period: 14 days ago → 8 days ago
    prev_start, prev_end = _date_range(14, 8)

    logger.info("Ads %s: %s–%s vs %s–%s", cid, curr_start, curr_end, prev_start, prev_end)

    client = _get_client()
    current = _run_summary(client, cid, curr_start, curr_end)
    previous = _run_summary(client, cid, prev_start, prev_end)
    top_campaigns = _run_top_campaigns(client, cid, curr_start, curr_end)

    return {
        "period": {"start": curr_start, "end": curr_end},
        "current": current,
        "previous": previous,
        "top_campaigns": top_campaigns,
    }
