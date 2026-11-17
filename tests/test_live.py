from __future__ import annotations

import os

import pytest

from kufar_client import KufarClient, SearchCriteria

pytestmark = pytest.mark.skipif(os.getenv("KUFAR_LIVE") != "1", reason="set KUFAR_LIVE=1 for real Kufar API tests")


@pytest.fixture(scope="module")
def client() -> KufarClient:
    instance = KufarClient(proxy=os.getenv("KUFAR_PROXY"), min_interval=0.5)
    yield instance
    instance.close()


@pytest.fixture(scope="module")
def criteria() -> SearchCriteria:
    return SearchCriteria.vitebsk_apartments(rooms=("2",), price_min=50_000, price_max=80_000)


@pytest.fixture(scope="module")
def first_page(client: KufarClient, criteria: SearchCriteria):
    return client.search(criteria, size=3)


def test_categories_live(client: KufarClient) -> None:
    categories = client.categories("недвиж")
    assert any(item.id == "1000" for item in categories)


def test_search_and_cursor_live(client: KufarClient, criteria: SearchCriteria, first_page) -> None:
    assert first_page.total > 0
    assert len(first_page.listings) == 3
    assert first_page.next_cursor
    second_page = client.search(criteria, size=3, cursor=first_page.next_cursor)
    assert second_page.listings
    assert {item.id for item in first_page.listings}.isdisjoint(item.id for item in second_page.listings)


def test_detail_live(client: KufarClient, first_page) -> None:
    expected = first_page.listings[0]
    detail = client.detail(expected.id)
    assert detail.id == expected.id
    assert detail.description
    assert detail.address
    assert detail.price_byn


def test_filters_live(client: KufarClient, criteria: SearchCriteria) -> None:
    filters = client.filters(criteria)
    by_query = {item.query_name: item for item in filters}
    assert "rms" in by_query
    assert "prc" in by_query
    assert "st" in by_query


def test_market_stats_live(client: KufarClient, criteria: SearchCriteria) -> None:
    stats = client.market_stats(criteria)
    assert stats.total > 0
    assert 0 < stats.priced_count <= stats.total
    assert stats.median_price_usd and 50_000 <= stats.median_price_usd <= 80_000


def test_suggestions_live(client: KufarClient) -> None:
    suggestions = client.suggestions("квартира")
    assert suggestions
    assert any("квартир" in item.label.casefold() for item in suggestions)


def test_map_live(client: KufarClient, criteria: SearchCriteria) -> None:
    page = client.map_search(criteria, size=2)
    assert page.total > 0
    assert page.listings
    lon, lat = page.listings[0].coordinates
    assert 29 < lon < 31
    assert 54 < lat < 56
