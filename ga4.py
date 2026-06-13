"""Google Analytics 4 data fetcher."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _get_client() -> BetaAnalyticsDataClient:
    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return BetaAnalyticsDataClient(credentials=creds)


def _date_range(offset_start: int, offset_end: int) -> tuple[str, str]:
    today = date.today()
    start = (today - timedelta(days=offset_start)).isoformat()
    end = (today - timedelta(days=offset_end)).isoformat()
    return start, end


def _run_summary(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start: str,
    end: str,
) -> dict[str, float]:
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start, end_date=end)],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="conversions"),
            Metric(name="purchaseRevenue"),
        ],
    )
    response = client.run_report(request)
    row = response.rows[0] if response.rows else None
    if row is None:
        return {"sessions": 0, "users": 0, "conversions": 0, "revenue": 0.0}
    values = [v.value for v in row.metric_values]
    return {
        "sessions": float(values[0]),
        "users": float(values[1]),
        "conversions": float(values[2]),
        "revenue": float(values[3]),
    }


def _run_channels(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=5,
    )
    response = client.run_report(request)
    channels = []
    for row in response.rows:
        channels.append(
            {
                "channel": row.dimension_values[0].value,
                "sessions": float(row.metric_values[0].value),
            }
        )
    return channels


def _run_top_pages(
    client: BetaAnalyticsDataClient,
    property_id: str,
    curr_start: str,
    curr_end: str,
    prev_start: str,
    prev_end: str,
) -> list[dict[str, Any]]:
    """Top 5 pages by pageviews this week, with previous-week comparison."""

    def _fetch_page_views(start: str, end: str, limit: int = 10) -> dict[str, int]:
        req = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews")],
            order_bys=[
                OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)
            ],
            limit=limit,
        )
        resp = client.run_report(req)
        return {
            row.dimension_values[0].value: int(float(row.metric_values[0].value))
            for row in resp.rows
        }

    curr_pages = _fetch_page_views(curr_start, curr_end, limit=5)
    # Fetch more from previous period so we can match all current top-5 pages
    prev_pages = _fetch_page_views(prev_start, prev_end, limit=20)

    pages = []
    for path, views in curr_pages.items():
        prev_views = prev_pages.get(path, 0)
        pages.append(
            {
                "path": path,
                "views": views,
                "views_prev": prev_views,
            }
        )
    return pages


def fetch(property_id: str) -> dict[str, Any]:
    """Fetch GA4 data for the last 7 full days plus the 7 days before that."""
    client = _get_client()

    curr_start, curr_end = _date_range(7, 1)
    prev_start, prev_end = _date_range(14, 8)

    logger.info("GA4 %s: %s–%s vs %s–%s", property_id, curr_start, curr_end, prev_start, prev_end)

    current = _run_summary(client, property_id, curr_start, curr_end)
    previous = _run_summary(client, property_id, prev_start, prev_end)
    channels = _run_channels(client, property_id, curr_start, curr_end)
    top_pages = _run_top_pages(client, property_id, curr_start, curr_end, prev_start, prev_end)

    return {
        "period": {"start": curr_start, "end": curr_end},
        "current": current,
        "previous": previous,
        "top_channels": channels,
        "top_pages": top_pages,
    }
