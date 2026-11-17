from __future__ import annotations

import os

from kufar_client import KufarClient, SearchCriteria

criteria = SearchCriteria.vitebsk_apartments(
    rooms=("2", "3"),
    price_min=45_000,
    price_max=85_000,
    total_area_min=45,
    not_first_floor=True,
    not_last_floor=True,
    only_with_photo=True,
)

with KufarClient(proxy=os.getenv("KUFAR_PROXY")) as client:
    page = client.search(criteria, size=10)
    stats = client.market_stats(criteria)
    print(f"Found: {page.total}; median USD: {stats.median_price_usd}")
    for listing in page.listings:
        print(listing.id, listing.price_usd, listing.rooms, listing.total_area, listing.address)
