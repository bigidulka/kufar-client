# Architecture

## Scope

`kufar-client` covers anonymous, read-only real-estate discovery on `re.kufar.by`. It does not authenticate users, reveal phone numbers, modify favourites, send messages, or publish ads.

The endpoint source of truth is the frontend bundle plus live replay, not official API documentation. See `endpoint_inventory.json` for per-route evidence and verification status.

## Modules

- `auth.py`: pluggable `AuthStrategy`; current public surface uses `NoAuth` (tier 0).
- `http.py`: `curl_cffi` transport, explicit proxy, Chrome TLS impersonation, pacing, retry and typed failures.
- `queries.py`: validated search criteria and Kufar filter encodings.
- `models.py`: categories, filter schema, listings, cursor pages, market stats, suggestions and map points.
- `client.py`: public facade over category, taxonomy, search, detail, pricing, suggestion and map endpoints.
- `cli.py`: one command for each facade capability with stable JSON/JSONL output.
- `html.py`: strict `__NEXT_DATA__` parser retained for diagnostics/fallback research; production methods use direct JSON APIs.

## Transport

`curl_cffi` runs with `impersonate="chrome"`. Public calls succeeded with plain curl as well, so TLS fingerprinting is not proven to be required; impersonation is retained because it matches the frontend and is cheap.

Proxy configuration is explicit. `trust_env=False` prevents an unrelated shell proxy from silently changing egress. A proxy URL is passed to both HTTP and HTTPS mappings. The CLI resolves `--proxy` or `KUFAR_PROXY`; `--no-proxy` forces no proxy.

The default interval is 0.5 seconds. Network exceptions and HTTP 5xx retry with bounded exponential backoff. HTTP 4xx do not retry. HTTP 429 raises `RateLimitError` immediately with `Retry-After`, if present. Exhausted retries always raise a typed error; no path returns `None`.

## Auth

Public category/search/detail/taxonomy/suggestion/map endpoints are tier 0. Successful external replay required no cookie, token, browser, timestamp or signature. The routing headers are public constants emitted by the bundle:

```text
X-Segmentation: routing=web_re;platform=web;application=ad_listing
```

Detail uses `application=ad_view` plus public app/source labels. The frontend can additionally attach a user `k_jwt`, but it is optional on this public surface and is not read from browser storage by this client.

## Search and pagination

The primary endpoint is `/search-api/v2/search/rendered-paginated`. It returns localized `ad_parameters`, `account_parameters` and:

```json
{"pagination":{"pages":[{"label":"next","num":2,"token":"..."}]}}
```

The token is opaque. Earlier code used `(page - 1) * 30`; the live server rejects that with HTTP 422 (`illegal base64`). `iter_search()` passes the returned token unchanged and stops on a missing or repeated token.

Kufar filter syntax used by `SearchCriteria`:

- ranges: `r:min,max`
- OR selections: `v.or:1,2`
- AND selections: `v.and:1,6`
- booleans: `1`

Price filter bounds are normal currency units. Response prices and map marker prices are minor units and are divided by 100 exactly once in the models.

## Taxonomy

`/taxonomy-proxy/v1/dispatch` returns references plus conditional rules, not a ready-made list. `filters()`:

1. Calculates the thousand-level parent (`1010 -> 1000`).
2. Fetches dispatch metadata for `ad_listing/web/web_re`.
3. Applies rules matching category, deal type, region and area.
4. Deduplicates by the declared key (`name`), allowing specific rules to override defaults.
5. Sorts selected definitions by `parameters_order`.

This avoids hardcoding labels and enum IDs that differ across apartments, houses, land and commercial property.

## Listing normalization

`Listing.from_raw()` accepts both flat raw records and rendered records. Rendered labels are preferred for wall material, repair, condition and amenities. Exact detail validates that the returned `ad_id` equals the requested ID; it never falls back to a text-search result.

Coordinates are normalized to `(longitude, latitude)`. Images become absolute RMS gallery URLs. Monetary model values are major units (for example `75000.0 USD`).

## Validation

`tests/test_unit.py` covers encoding, rendered parsing, taxonomy rule resolution, SSR diagnostics and strict ID extraction. `tests/test_live.py` calls every public client method against the real target and checks cursor separation, exact detail, filter availability, price stats, suggestions and Vitebsk map coordinates.

Rate measurements and the chosen throttle are stored in `rate_limit_measurement.json`.
