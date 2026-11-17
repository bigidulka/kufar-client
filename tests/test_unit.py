from __future__ import annotations

from kufar_client.client import KufarClient
from kufar_client.html import extract_next_data
from kufar_client.models import Listing
from kufar_client.queries import SearchCriteria


def test_search_criteria_encodes_realty_filters() -> None:
    criteria = SearchCriteria.vitebsk_apartments(
        rooms=("1", "2"),
        price_min=50_000,
        price_max=80_000,
        total_area_min=40,
        total_area_max=70,
        improvements=("1", "6"),
        not_first_floor=True,
        extra={"custom": "v.or:7"},
    )
    params = dict(criteria.to_params(size=25, cursor="opaque=="))
    assert params["cat"] == "1010"
    assert params["rgn"] == "6"
    assert params["ar"] == "18"
    assert params["prc"] == "r:50000,80000"
    assert params["cur"] == "USD"
    assert params["rms"] == "v.or:1,2"
    assert params["st"] == "r:40,70"
    assert params["fbi"] == "v.and:1,6"
    assert params["nff"] == "1"
    assert params["cursor"] == "opaque=="
    assert params["custom"] == "v.or:7"


def test_listing_parses_rendered_shape() -> None:
    listing = Listing.from_raw(
        {
            "ad_id": 123456789,
            "subject": "Test apartment",
            "ad_link": "https://re.kufar.by/vi/123456789",
            "price_byn": "12000000",
            "price_usd": "4000000",
            "calculator": [{"currency": "BYN", "price": "12000000", "price_per_meter": "200000"}],
            "images": [{"path": "adim1/example.jpg"}],
            "ad_parameters": [
                {"p": "category", "v": 1010, "vl": "Квартиры"},
                {"p": "type", "v": "sell", "vl": "Продажа"},
                {"p": "rooms", "v": "2", "vl": "2"},
                {"p": "size", "v": 60, "vl": ""},
                {"p": "coordinates", "v": [30.2, 55.2], "vl": ["", ""]},
                {"p": "flat_repair", "v": "5", "vl": "Евро"},
            ],
            "account_parameters": [{"p": "address", "v": "Витебск", "vl": ""}],
        }
    )
    assert listing.id == "123456789"
    assert listing.price_byn == 120000.0
    assert listing.price_usd == 40000.0
    assert listing.price_per_m2_byn == 2000.0
    assert listing.rooms == "2"
    assert listing.total_area == 60.0
    assert listing.coordinates == (30.2, 55.2)
    assert listing.repair == "Евро"
    assert listing.address == "Витебск"
    assert listing.images == ["https://rms.kufar.by/v1/gallery/adim1/example.jpg"]


def test_taxonomy_rules_apply_specific_overrides() -> None:
    payload = {
        "metadata": {
            "parameters": {
                "refs": {
                    "1": {"variation_id": 1, "name": "rooms", "url_name": "rms", "labels": {"name": {"ru": "Default"}}},
                    "2": {"variation_id": 2, "name": "rooms", "url_name": "rms", "labels": {"name": {"ru": "Apartments"}}},
                    "3": {"variation_id": 3, "name": "size", "url_name": "st", "labels": {"name": {"ru": "Area"}}},
                },
                "rules": [
                    {"rule": {}, "refs": ["1", "3"]},
                    {"rule": {"category": "1010", "type": "sell"}, "refs": ["2"]},
                ],
            },
            "parameters_order": {"refs": {"0": ["2", "3", "1"]}},
        }
    }
    resolved = KufarClient._resolve_taxonomy(payload, {"category": "1010", "type": "sell"})
    assert [item["variation_id"] for item in resolved] == [2, 3]


def test_extract_next_data_uses_json_script() -> None:
    data = extract_next_data('<script id="__NEXT_DATA__" type="application/json">{"props":{"ok":true}}</script>')
    assert data["props"]["ok"] is True


def test_listing_id_is_strict() -> None:
    assert KufarClient._listing_id("https://re.kufar.by/vi/vitebsk/kupit/kvartiru/1085104008") == "1085104008"
