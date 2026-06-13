"""Google Search Console data fetcher."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _get_service() -> Any:
    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return build("searchconsole", "v1", credentials=creds)


def _date_range(offset_start: int, offset_end: int) -> tuple[str, str]:
    today = date.today()
    start = (today - timedelta(days=offset_start)).isoformat()
    end = (today - timedelta(days=offset_end)).isoformat()
    return start, end


def _run_summary(service: Any, site_url: str, start: str, end: str) -> dict[str, float]:
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": [],
        "rowLimit": 1,
    }
    response = (
        service.searchanalytics()
        .query(siteUrl=site_url, body=body)
        .execute()
    )
    rows = response.get("rows", [])
    if not rows:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    r = rows[0]
    return {
        "clicks": r.get("clicks", 0),
        "impressions": r.get("impressions", 0),
        "ctr": round(r.get("ctr", 0.0) * 100, 2),
        "position": round(r.get("position", 0.0), 1),
    }


def _run_top_queries(service: Any, site_url: str, start: str, end: str) -> list[dict[str, Any]]:
    # Note: the GSC API does not support an orderBy field; results are returned
    # in descending click order by default when the query dimension is used.
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": ["query"],
        "rowLimit": 5,
    }
    response = (
        service.searchanalytics()
        .query(siteUrl=site_url, body=body)
        .execute()
    )
    queries = []
    for row in response.get("rows", []):
        queries.append(
            {
                "query": row["keys"][0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0.0) * 100, 2),
                "position": round(row.get("position", 0.0), 1),
            }
        )
    return queries


def fetch(site_url: str) -> dict[str, Any]:
    """Fetch GSC data for the last 7 full days vs the 7 days before that.

    Matches the GA4 comparison window exactly (yesterday − 6 → yesterday).
    Note: GSC has a ~3-day data delay, so the most recent days may still be
    incomplete, but the period is kept consistent with all other sources.
    """
    service = _get_service()

    # Current period: 7 days ago → yesterday
    curr_start, curr_end = _date_range(7, 1)
    # Previous period: 14 days ago → 8 days ago
    prev_start, prev_end = _date_range(14, 8)

    logger.info("GSC %s: %s–%s vs %s–%s", site_url, curr_start, curr_end, prev_start, prev_end)

    current = _run_summary(service, site_url, curr_start, curr_end)
    previous = _run_summary(service, site_url, prev_start, prev_end)
    top_queries = _run_top_queries(service, site_url, curr_start, curr_end)

    return {
        "period": {"start": curr_start, "end": curr_end},
        "current": current,
        "previous": previous,
        "top_queries": top_queries,
    }
