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
    """Fetch top 5 campaigns by spend, including impression share metrics."""
    ga_service = client.get_service("GoogleAdsService")

    # Note: search_impression_share and lost IS are only available at campaign level,
    # not at the customer resource level.
    query = f"""
        SELECT
            campaign.name,
            metrics.clicks,
            metrics.impressions,
            metrics.cost_micros,
            metrics.conversions,
            metrics.search_impression_share,
            metrics.search_budget_lost_impression_share,
            metrics.search_rank_lost_impression_share
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

        # Impression share values are floats 0–1; the API returns a sentinel
        # value of 0.1 for "<10%" and may be None/0 when not enough data.
        def _pct(val: float) -> float | None:
            """Convert 0–1 fraction to rounded percentage, or None if unavailable."""
            if val is None or val == 0.0:
                return None
            return round(val * 100, 1)

        campaigns.append(
            {
                "name": row.campaign.name,
                "clicks": int(m.clicks),
                "impressions": int(m.impressions),
                "cost_eur": round(m.cost_micros / 1_000_000, 2),
                "conversions": round(m.conversions, 1),
                "search_impression_share_pct": _pct(m.search_impression_share),
                "lost_is_budget_pct": _pct(m.search_budget_lost_impression_share),
                "lost_is_rank_pct": _pct(m.search_rank_lost_impression_share),
            }
        )
    return campaigns


def _compute_account_impression_share(campaigns: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute impression-weighted average IS across campaigns."""
    total_imp = sum(c["impressions"] for c in campaigns)
    if total_imp == 0:
        return {}

    def _wavg(key: str) -> float | None:
        values = [(c[key], c["impressions"]) for c in campaigns if c.get(key) is not None]
        if not values:
            return None
        weighted = sum(v * imp for v, imp in values)
        weight = sum(imp for _, imp in values)
        return round(weighted / weight, 1) if weight else None

    result: dict[str, Any] = {}
    avg_is = _wavg("search_impression_share_pct")
    avg_lost_budget = _wavg("lost_is_budget_pct")
    avg_lost_rank = _wavg("lost_is_rank_pct")

    if avg_is is not None:
        result["search_impression_share_pct"] = avg_is
    if avg_lost_budget is not None:
        result["lost_is_budget_pct"] = avg_lost_budget
    if avg_lost_rank is not None:
        result["lost_is_rank_pct"] = avg_lost_rank

    return result


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

    curr_start, curr_end = _date_range(7, 1)
    prev_start, prev_end = _date_range(14, 8)

    logger.info("Ads %s: %s–%s vs %s–%s", cid, curr_start, curr_end, prev_start, prev_end)

    client = _get_client()
    current = _run_summary(client, cid, curr_start, curr_end)
    previous = _run_summary(client, cid, prev_start, prev_end)
    top_campaigns = _run_top_campaigns(client, cid, curr_start, curr_end)
    account_is = _compute_account_impression_share(top_campaigns)

    return {
        "period": {"start": curr_start, "end": curr_end},
        "current": current,
        "previous": previous,
        "account_impression_share": account_is,
        "top_campaigns": top_campaigns,
    }
