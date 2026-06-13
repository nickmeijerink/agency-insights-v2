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


def _run_queries(service: Any, site_url: str, start: str, end: str, limit: int = 10) -> dict[str, dict]:
    """Fetch queries and return as {query: metrics} dict for easy joining."""
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": ["query"],
        "rowLimit": limit,
    }
    response = (
        service.searchanalytics()
        .query(siteUrl=site_url, body=body)
        .execute()
    )
    result = {}
    for row in response.get("rows", []):
        query = row["keys"][0]
        result[query] = {
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": round(row.get("ctr", 0.0) * 100, 2),
            "position": round(row.get("position", 0.0), 1),
        }
    return result


def _run_top_queries_compared(
    service: Any,
    site_url: str,
    curr_start: str,
    curr_end: str,
    prev_start: str,
    prev_end: str,
) -> list[dict[str, Any]]:
    """Top 5 queries by clicks this week, with previous-week comparison."""
    curr = _run_queries(service, site_url, curr_start, curr_end, limit=5)
    # Fetch more from prev so we can match all current top-5 queries
    prev = _run_queries(service, site_url, prev_start, prev_end, limit=20)

    results = []
    for query, metrics in curr.items():
        prev_metrics = prev.get(query, {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0})
        clicks_delta = metrics["clicks"] - prev_metrics["clicks"]
        # Positive position_delta = moved up in rankings (lower number = better)
        position_delta = round(prev_metrics["position"] - metrics["position"], 1)
        results.append(
            {
                "query": query,
                "clicks": metrics["clicks"],
                "impressions": metrics["impressions"],
                "ctr": metrics["ctr"],
                "position": metrics["position"],
                "prev_clicks": prev_metrics["clicks"],
                "prev_position": prev_metrics["position"],
                "clicks_delta": clicks_delta,
                "position_delta": position_delta,  # positive = ranking improved
            }
        )
    return results


def fetch(site_url: str) -> dict[str, Any]:
    """Fetch GSC data for the last 7 full days vs the 7 days before that."""
    service = _get_service()

    curr_start, curr_end = _date_range(7, 1)
    prev_start, prev_end = _date_range(14, 8)

    logger.info("GSC %s: %s–%s vs %s–%s", site_url, curr_start, curr_end, prev_start, prev_end)

    current = _run_summary(service, site_url, curr_start, curr_end)
    previous = _run_summary(service, site_url, prev_start, prev_end)
    top_queries = _run_top_queries_compared(
        service, site_url, curr_start, curr_end, prev_start, prev_end
    )

    return {
        "period": {"start": curr_start, "end": curr_end},
        "current": current,
        "previous": previous,
        "top_queries": top_queries,
    }
