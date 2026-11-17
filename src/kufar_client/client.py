from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, Self

from .exceptions import NotFoundError, ParseError
from .http import Transport
from .models import (
    Category,
    FilterDefinition,
    Listing,
    MapListing,
    MapPage,
    MarketStats,
    PaginationLink,
    SearchPage,
    Suggestion,
    flatten_categories,
)
from .queries import SearchCriteria

API_URL = "https://api.kufar.by"
REALTY_URL = "https://re.kufar.by"
VITEBSK_APARTMENTS_URL = f"{REALTY_URL}/l/vitebsk/kupit/kvartiru"


def _segmentation(application: str) -> dict[str, str]:
    return {
        "Origin": REALTY_URL,
        "X-Segmentation": f"routing=web_re;platform=web;application={application}",
    }


class KufarClient:
    def __init__(
        self,
        *,
        proxy: str | None = None,
        timeout: float = 30.0,
        min_interval: float = 0.5,
        retries: int = 3,
    ) -> None:
        self.http = Transport(
            API_URL,
            proxy=proxy,
            timeout=timeout,
            min_interval=min_interval,
            retries=retries,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def categories(self, query: str = "") -> list[Category]:
        data = self.http.get_json("/category-tree/v1/category_tree")
        tree = [Category.from_raw(item) for item in data.get("categories") or [] if isinstance(item, dict)]
        if not query:
            return tree
        normalized = query.casefold().replace("ё", "е")
        return [
            category
            for category in flatten_categories(tree)
            if normalized in f"{category.id} {category.title}".casefold().replace("ё", "е")
        ]

    def filters(self, criteria: SearchCriteria | None = None) -> list[FilterDefinition]:
        criteria = criteria or SearchCriteria.vitebsk_apartments()
        parent = str((int(criteria.category) // 1000) * 1000)
        payload = self.http.get_json(
            "/taxonomy-proxy/v1/dispatch",
            params={
                "parent": parent,
                "application": "ad_listing",
                "platform": "web",
                "routing": "web_re",
            },
            referer=VITEBSK_APARTMENTS_URL,
            extra_headers=_segmentation("ad_listing"),
        )
        raw_filters = self._resolve_taxonomy(
            payload,
            {
                "parent_category": parent,
                "category": criteria.category,
                "type": criteria.deal_type,
                "region": criteria.region,
                "area": criteria.area,
            },
        )
        return [FilterDefinition.from_raw(item) for item in raw_filters]

    def search(
        self,
        criteria: SearchCriteria | None = None,
        *,
        cursor: str | None = None,
        size: int = 30,
    ) -> SearchPage:
        if not 1 <= size <= 100:
            raise ValueError("search size must be between 1 and 100")
        criteria = criteria or SearchCriteria.vitebsk_apartments()
        payload = self.http.get_json(
            "/search-api/v2/search/rendered-paginated",
            params=criteria.to_params(size=size, cursor=cursor),
            referer=VITEBSK_APARTMENTS_URL,
            extra_headers=_segmentation("ad_listing"),
        )
        listings = [Listing.from_raw(item) for item in payload.get("ads") or [] if isinstance(item, dict)]
        pages = ((payload.get("pagination") or {}).get("pages") or [])
        pagination = [
            PaginationLink(
                label=str(item.get("label") or ""),
                page=int(item.get("num") or 0),
                token=str(item["token"]) if item.get("token") else None,
            )
            for item in pages
            if isinstance(item, dict)
        ]
        return SearchPage(total=int(payload.get("total") or 0), listings=listings, pagination=pagination)

    def iter_search(
        self,
        criteria: SearchCriteria | None = None,
        *,
        cursor: str | None = None,
        size: int = 30,
        max_pages: int | None = None,
    ) -> Iterator[SearchPage]:
        seen: set[str] = set()
        current = cursor
        page_count = 0
        while max_pages is None or page_count < max_pages:
            page = self.search(criteria, cursor=current, size=size)
            yield page
            page_count += 1
            next_cursor = page.next_cursor
            if not next_cursor or next_cursor in seen:
                return
            seen.add(next_cursor)
            current = next_cursor

    def detail(self, id_or_url: str | int) -> Listing:
        requested_id = self._listing_id(id_or_url)
        payload = self.http.get_json(
            f"/search-api/v2/item/{requested_id}/rendered",
            params={"lang": "ru"},
            referer=f"{REALTY_URL}/vi/{requested_id}",
            extra_headers={
                **_segmentation("ad_view"),
                "X-App-Request-Source": "ad_view",
                "X-App-Name": "Web Kufar",
            },
        )
        raw = payload.get("result")
        if not isinstance(raw, dict):
            raise NotFoundError(f"Kufar listing {requested_id} was not found")
        actual_id = str(raw.get("ad_id") or raw.get("list_id") or "")
        if actual_id != requested_id:
            raise ParseError(f"Kufar detail ID mismatch: requested {requested_id}, received {actual_id}")
        return Listing.from_raw(raw)

    def market_stats(self, criteria: SearchCriteria | None = None) -> MarketStats:
        criteria = criteria or SearchCriteria.vitebsk_apartments()
        params = [
            (key, value)
            for key, value in criteria.to_params(size=1)
            if key not in {"size", "sort", "cursor"}
        ]
        request_options = {
            "params": params,
            "referer": VITEBSK_APARTMENTS_URL,
            "extra_headers": _segmentation("ad_listing"),
        }
        count = self.http.get_json("/search-api/v2/search/count", **request_options)
        median = self.http.get_json("/search-api/v2/search/median-price", **request_options)
        return MarketStats.from_raw(count, median)

    def suggestions(self, query: str) -> list[Suggestion]:
        if not query.strip():
            return []
        payload = self.http.get_json(
            "/search-api/v1/info/text-suggest-extend",
            params={"query": query.strip()},
            referer=VITEBSK_APARTMENTS_URL,
            extra_headers=_segmentation("ad_listing"),
        )
        result = payload.get("result") or {}
        return [
            Suggestion.from_raw(item)
            for item in result.get("suggestions") or []
            if isinstance(item, dict)
        ]

    def map_search(
        self,
        criteria: SearchCriteria | None = None,
        *,
        size: int = 500,
        bbox: str | None = None,
    ) -> MapPage:
        if not 1 <= size <= 900:
            raise ValueError("map size must be between 1 and 900")
        criteria = criteria or SearchCriteria.vitebsk_apartments()
        params = criteria.to_params(size=size)
        if bbox:
            params.append(("gbx", bbox))
        payload = self.http.get_json(
            "/search-api/v2/search/map/over",
            params=params,
            referer=f"{REALTY_URL}/map",
            extra_headers=_segmentation("ad_listing"),
        )
        listings = [MapListing.from_raw(item) for item in payload.get("ads") or [] if isinstance(item, dict)]
        return MapPage(total=int(payload.get("total") or 0), listings=listings)

    @staticmethod
    def _resolve_taxonomy(payload: dict[str, Any], context: dict[str, str]) -> list[dict[str, Any]]:
        metadata = payload.get("metadata") or {}
        parameters = metadata.get("parameters") or {}
        refs = parameters.get("refs") or {}
        selected: dict[str, dict[str, Any]] = {}

        for entry in parameters.get("rules") or []:
            if not isinstance(entry, dict):
                continue
            rule = entry.get("rule") or {}
            if not KufarClient._rule_matches(rule, context):
                continue
            for ref_id in entry.get("refs") or []:
                raw = refs.get(str(ref_id))
                if isinstance(raw, dict) and raw.get("name"):
                    selected[str(raw["name"])] = raw

        order_meta = metadata.get("parameters_order") or {}
        order_refs = order_meta.get("refs") or {}
        order_ids = order_refs.get("0") or []
        rank = {str(ref_id): index for index, ref_id in enumerate(order_ids)}
        return sorted(
            selected.values(),
            key=lambda item: rank.get(str(item.get("variation_id")), len(rank)),
        )

    @staticmethod
    def _rule_matches(rule: dict[str, Any], context: dict[str, str]) -> bool:
        for key, expected in rule.items():
            actual = context.get(str(key))
            if isinstance(expected, list):
                if actual not in {str(item) for item in expected}:
                    return False
            elif isinstance(expected, dict) or actual != str(expected):
                return False
        return True

    @staticmethod
    def _listing_id(id_or_url: str | int) -> str:
        text = str(id_or_url).strip()
        if text.isdigit():
            return text
        matches = re.findall(r"(?<!\d)(\d{6,})(?!\d)", text)
        if not matches:
            raise ValueError(f"cannot extract Kufar listing ID from: {id_or_url}")
        return matches[-1]
