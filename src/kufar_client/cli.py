from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .client import KufarClient
from .exceptions import ApiError, KufarError, RateLimitError
from .models import Category, Listing, flatten_categories
from .queries import CATEGORY_IDS, SearchCriteria


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _extra_filters(items: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        key, separator, value = item.partition("=")
        if not separator or not key.strip() or not value.strip():
            raise ValueError(f"invalid --filter {item!r}; expected KEY=VALUE")
        result[key.strip()] = value.strip()
    return result


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _print_category(category: Category, depth: int = 0) -> None:
    print(f"{'  ' * depth}{category.id}\t{category.title}")
    for child in category.children:
        _print_category(child, depth + 1)


def _print_listing(listing: Listing) -> None:
    price = f"${listing.price_usd:,.0f}" if listing.price_usd is not None else "price ?"
    details = " / ".join(
        item
        for item in (
            f"{listing.rooms} rooms" if listing.rooms else "",
            f"{listing.total_area:g} m2" if listing.total_area is not None else "",
            f"floor {listing.floor}/{listing.floors}" if listing.floor and listing.floors else "",
        )
        if item
    )
    print(f"{listing.id}  {price}  {listing.title}")
    if details:
        print(f"  {details}")
    if listing.address:
        print(f"  {listing.address}")
    print(f"  {listing.url}")


def _common_output(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true")
    group.add_argument("--jsonl", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kufar", description="Unofficial read-only Kufar real-estate CLI")
    parser.add_argument("--proxy", default=os.getenv("KUFAR_PROXY"), help="explicit HTTP/SOCKS proxy URL")
    parser.add_argument("--no-proxy", action="store_true", help="ignore KUFAR_PROXY and connect directly")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--min-interval", type=float, default=0.5, help="minimum seconds between requests")
    subparsers = parser.add_subparsers(dest="command", required=True)

    categories = subparsers.add_parser("categories", help="list or search Kufar categories")
    categories.add_argument("query", nargs="?", default="")
    categories.add_argument("--flat", action="store_true")
    _common_output(categories)

    filters = subparsers.add_parser("filters", help="show Vitebsk real-estate filter schema")
    filters.add_argument("--category", default="apartments", choices=sorted(CATEGORY_IDS))
    filters.add_argument("--query", default="", help="filter by query name or Russian label")
    _common_output(filters)

    search = subparsers.add_parser("search", help="search Vitebsk real estate")
    search.add_argument("--category", default="apartments", choices=sorted(CATEGORY_IDS))
    search.add_argument("--query", default="")
    search.add_argument("--sort", choices=["date", "price-asc", "price-desc"], default="date")
    search.add_argument("--price-currency", choices=["USD", "BYN"], default="USD")
    search.add_argument("--price-min", type=float)
    search.add_argument("--price-max", type=float)
    search.add_argument("--rooms", default="")
    search.add_argument("--area-min", type=float)
    search.add_argument("--area-max", type=float)
    search.add_argument("--living-area-min", type=float)
    search.add_argument("--living-area-max", type=float)
    search.add_argument("--kitchen-area-min", type=float)
    search.add_argument("--kitchen-area-max", type=float)
    search.add_argument("--floor-min", type=int)
    search.add_argument("--floor-max", type=int)
    search.add_argument("--floors-min", type=int)
    search.add_argument("--floors-max", type=int)
    search.add_argument("--year-min", type=int)
    search.add_argument("--year-max", type=int)
    search.add_argument("--wall", default="", help="wall material IDs, comma-separated")
    search.add_argument("--repair", default="", help="repair IDs, comma-separated")
    search.add_argument("--condition", choices=["new", "secondary", ""], default="")
    search.add_argument("--improvement", default="", help="required improvement IDs, comma-separated")
    search.add_argument("--not-first-floor", action="store_true")
    search.add_argument("--not-last-floor", action="store_true")
    search.add_argument("--new-building", action="store_true")
    search.add_argument("--company-only", action="store_true")
    search.add_argument("--only-with-photo", action="store_true")
    search.add_argument("--filter", action="append", default=[], metavar="KEY=VALUE")
    search.add_argument("--cursor")
    search.add_argument("--size", type=int, default=30)
    search.add_argument("--pages", type=int, default=1)
    search.add_argument("--limit", type=int, default=0, help="maximum listings printed; 0 means all fetched")
    _common_output(search)

    stats = subparsers.add_parser("stats", help="count listings and calculate median asking price")
    stats.add_argument("--category", default="apartments", choices=sorted(CATEGORY_IDS))
    stats.add_argument("--query", default="")
    stats.add_argument("--rooms", default="")
    stats.add_argument("--area-min", type=float)
    stats.add_argument("--area-max", type=float)
    _common_output(stats)

    suggest = subparsers.add_parser("suggest", help="get Kufar search suggestions")
    suggest.add_argument("query")
    _common_output(suggest)

    map_parser = subparsers.add_parser("map", help="get compact real-estate map points")
    map_parser.add_argument("--category", default="apartments", choices=sorted(CATEGORY_IDS))
    map_parser.add_argument("--query", default="")
    map_parser.add_argument("--rooms", default="")
    map_parser.add_argument("--price-currency", choices=["USD", "BYN"], default="USD")
    map_parser.add_argument("--price-min", type=float)
    map_parser.add_argument("--price-max", type=float)
    map_parser.add_argument("--bbox", help="Kufar gbx bounding-box value")
    map_parser.add_argument("--size", type=int, default=500)
    _common_output(map_parser)

    detail = subparsers.add_parser("detail", help="fetch exact listing by ID or URL")
    detail.add_argument("listing")
    _common_output(detail)
    return parser


def _criteria(args: argparse.Namespace) -> SearchCriteria:
    condition = {"new": "2", "secondary": "1", "": ""}[args.condition]
    return SearchCriteria.vitebsk_apartments(
        category=args.category,
        query=args.query,
        sort=args.sort,
        price_currency=args.price_currency,
        price_min=args.price_min,
        price_max=args.price_max,
        rooms=_csv(args.rooms),
        total_area_min=args.area_min,
        total_area_max=args.area_max,
        living_area_min=args.living_area_min,
        living_area_max=args.living_area_max,
        kitchen_area_min=args.kitchen_area_min,
        kitchen_area_max=args.kitchen_area_max,
        floor_min=args.floor_min,
        floor_max=args.floor_max,
        floors_min=args.floors_min,
        floors_max=args.floors_max,
        year_min=args.year_min,
        year_max=args.year_max,
        wall_materials=_csv(args.wall),
        repairs=_csv(args.repair),
        condition=condition,
        improvements=_csv(args.improvement),
        not_first_floor=args.not_first_floor,
        not_last_floor=args.not_last_floor,
        new_building=args.new_building,
        company_only=args.company_only,
        only_with_photo=args.only_with_photo,
        extra=_extra_filters(args.filter),
    )


def run(args: argparse.Namespace) -> int:
    proxy = None if args.no_proxy else args.proxy
    with KufarClient(
        proxy=proxy,
        timeout=args.timeout,
        min_interval=args.min_interval,
    ) as client:
        if args.command == "categories":
            categories = client.categories(args.query)
            rows = flatten_categories(categories) if args.flat and not args.query else categories
            if args.json or args.jsonl:
                payload = [item.to_dict() for item in rows]
                if args.jsonl:
                    for item in payload:
                        print(json.dumps(item, ensure_ascii=False))
                else:
                    _json(payload)
            else:
                for category in rows:
                    _print_category(category)
            return 0

        if args.command == "filters":
            criteria = SearchCriteria.vitebsk_apartments(category=args.category)
            filters = client.filters(criteria)
            if args.query:
                query = args.query.casefold()
                filters = [item for item in filters if query in f"{item.name} {item.query_name} {item.label}".casefold()]
            if args.json or args.jsonl:
                payload = [item.to_dict() for item in filters]
                if args.jsonl:
                    for item in payload:
                        print(json.dumps(item, ensure_ascii=False))
                else:
                    _json(payload)
            else:
                for item in filters:
                    options = ", ".join(f"{option.value}={option.label}" for option in item.options[:8])
                    print(f"{item.query_name}\t{item.label}\t{item.mode}\t{options}")
            return 0

        if args.command == "stats":
            criteria = SearchCriteria.vitebsk_apartments(
                category=args.category,
                query=args.query,
                rooms=_csv(args.rooms),
                total_area_min=args.area_min,
                total_area_max=args.area_max,
            )
            stats = client.market_stats(criteria)
            if args.json or args.jsonl:
                print(json.dumps(stats.to_dict(), ensure_ascii=False, indent=None if args.jsonl else 2))
            else:
                print(f"total\t{stats.total}")
                print(f"priced\t{stats.priced_count}")
                print(f"median_usd\t{stats.median_price_usd}")
                print(f"median_byn\t{stats.median_price_byn}")
            return 0

        if args.command == "suggest":
            suggestions = client.suggestions(args.query)
            payload = [item.to_dict() for item in suggestions]
            if args.jsonl:
                for item in payload:
                    print(json.dumps(item, ensure_ascii=False))
            elif args.json:
                _json(payload)
            else:
                for item in suggestions:
                    print(f"{item.label}\t{item.preferred_category}\t{item.kind}")
            return 0

        if args.command == "map":
            criteria = SearchCriteria.vitebsk_apartments(
                category=args.category,
                query=args.query,
                rooms=_csv(args.rooms),
                price_currency=args.price_currency,
                price_min=args.price_min,
                price_max=args.price_max,
            )
            page = client.map_search(criteria, size=args.size, bbox=args.bbox)
            if args.jsonl:
                for item in page.listings:
                    print(json.dumps(item.to_dict(), ensure_ascii=False))
            elif args.json:
                _json(page.to_dict())
            else:
                for item in page.listings:
                    lon, lat = item.coordinates
                    print(f"{item.id}\t{item.price_byn or ''}\t{lon},{lat}")
                print(f"# total={page.total} fetched={len(page.listings)}", file=sys.stderr)
            return 0

        if args.command == "detail":
            listing = client.detail(args.listing)
            if args.json or args.jsonl:
                payload = listing.to_dict()
                print(json.dumps(payload, ensure_ascii=False, indent=None if args.jsonl else 2))
            else:
                _print_listing(listing)
                if listing.description:
                    print(f"\n{listing.description}")
            return 0

        if args.command == "search":
            if args.pages < 1:
                raise ValueError("--pages must be at least 1")
            criteria = _criteria(args)
            pages = list(
                client.iter_search(
                    criteria,
                    cursor=args.cursor,
                    size=args.size,
                    max_pages=args.pages,
                )
            )
            listings = [listing for page in pages for listing in page.listings]
            if args.limit:
                listings = listings[: args.limit]
            if args.jsonl:
                for listing in listings:
                    print(json.dumps(listing.to_dict(), ensure_ascii=False))
            elif args.json:
                _json(
                    {
                        "total": pages[0].total if pages else 0,
                        "fetched": len(listings),
                        "next_cursor": pages[-1].next_cursor if pages else None,
                        "listings": [listing.to_dict() for listing in listings],
                    }
                )
            else:
                for listing in listings:
                    _print_listing(listing)
                if pages:
                    print(f"# total={pages[0].total} fetched={len(listings)} next_cursor={pages[-1].next_cursor or ''}", file=sys.stderr)
            return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except RateLimitError as exc:
        message = {"error": str(exc), "status": exc.status, "retry_after": exc.retry_after}
        print(json.dumps(message, ensure_ascii=False), file=sys.stderr)
        return 3
    except ApiError as exc:
        message = {"error": str(exc), "status": exc.status, "payload": exc.payload}
        print(json.dumps(message, ensure_ascii=False), file=sys.stderr)
        return 1
    except (KufarError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
