from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

RMS_GALLERY = "https://rms.kufar.by/v1/gallery/"


def _minor_units(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value) / 100.0, 2)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _parameter_maps(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    values: dict[str, Any] = {}
    labels: dict[str, Any] = {}
    for item in raw.get("ad_parameters") or []:
        if not isinstance(item, dict) or not item.get("p"):
            continue
        key = str(item["p"])
        values[key] = item.get("v")
        labels[key] = item.get("vl")
    for item in raw.get("account_parameters") or []:
        if not isinstance(item, dict) or not item.get("p"):
            continue
        key = str(item["p"])
        values[key] = item.get("v")
        labels[key] = item.get("vl")
    return values, labels


def _images(raw: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in raw.get("images") or []:
        path = item.get("path") if isinstance(item, dict) else item
        if not path:
            continue
        text = str(path)
        result.append(text if text.startswith("http") else f"{RMS_GALLERY}{text.lstrip('/')}")
    return result


def _calculator_value(raw: dict[str, Any], currency: str, key: str = "price") -> float | None:
    for item in raw.get("calculator") or []:
        if isinstance(item, dict) and item.get("currency") == currency:
            return _minor_units(item.get(key))
    return None


def _as_text_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


@dataclass(slots=True)
class Category:
    id: str
    title: str
    parent_id: str | None = None
    children: list[Category] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any], parent_id: str | None = None) -> Category:
        category = cls(
            id=str(raw.get("id") or ""),
            title=str(raw.get("name_ru") or raw.get("name") or raw.get("id") or ""),
            parent_id=parent_id,
        )
        category.children = [
            cls.from_raw(item, category.id)
            for item in raw.get("subcategories") or []
            if isinstance(item, dict)
        ]
        return category

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "parent_id": self.parent_id,
            "children": [item.to_dict() for item in self.children],
        }


@dataclass(slots=True)
class FilterOption:
    value: str
    label: str


@dataclass(slots=True)
class FilterDefinition:
    name: str
    query_name: str
    label: str
    value_type: str
    mode: str
    multi: bool
    options: list[FilterOption] = field(default_factory=list)
    range: dict[str, Any] | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> FilterDefinition:
        labels = raw.get("labels") or {}
        name_labels = labels.get("name") or {}
        options = []
        for item in raw.get("values") or []:
            if not isinstance(item, dict):
                continue
            option_labels = item.get("labels") or {}
            options.append(FilterOption(str(item.get("value", "")), str(option_labels.get("ru") or "")))
        return cls(
            name=str(raw.get("name") or ""),
            query_name=str(raw.get("url_name") or ""),
            label=str(name_labels.get("ru") or raw.get("name") or ""),
            value_type=str(raw.get("type") or ""),
            mode=str(raw.get("meta") or ""),
            multi=bool(raw.get("multi")),
            options=options,
            range=raw.get("range") if isinstance(raw.get("range"), dict) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["options"] = [asdict(option) for option in self.options]
        return data


@dataclass(slots=True)
class Listing:
    id: str
    title: str
    url: str
    category_id: str
    deal_type: str
    description: str = ""
    address: str = ""
    coordinates: tuple[float, float] | None = None
    price_byn: float | None = None
    price_usd: float | None = None
    price_per_m2_byn: float | None = None
    rooms: str = ""
    total_area: float | None = None
    living_area: float | None = None
    kitchen_area: float | None = None
    floor: int | None = None
    floors: int | None = None
    year_built: int | None = None
    wall_material: str = ""
    condition: str = ""
    repair: str = ""
    bathroom: str = ""
    balcony: str = ""
    improvements: list[str] = field(default_factory=list)
    seller_name: str = ""
    contact_person: str = ""
    is_company: bool = False
    created_at: str = ""
    listed_at: str = ""
    images: list[str] = field(default_factory=list)
    phone_hidden: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    parameter_labels: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Listing:
        values, labels = _parameter_maps(raw)

        def value(name: str, default: Any = None) -> Any:
            current = raw.get(name)
            return current if current not in (None, "") else values.get(name, default)

        def display(name: str) -> str:
            current = labels.get(name)
            if isinstance(current, list):
                return ", ".join(str(item) for item in current)
            if current not in (None, ""):
                return str(current)
            raw_value = value(name, "")
            if isinstance(raw_value, list):
                return ", ".join(str(item) for item in raw_value)
            return str(raw_value or "")

        coordinates = value("coordinates")
        normalized_coordinates = None
        if isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
            try:
                normalized_coordinates = (float(coordinates[0]), float(coordinates[1]))
            except (TypeError, ValueError):
                pass

        ad_id = str(raw.get("ad_id") or raw.get("list_id") or "")
        price_byn = _calculator_value(raw, "BYN") or _minor_units(raw.get("price_byn"))
        price_usd = _calculator_value(raw, "USD") or _minor_units(raw.get("price_usd"))
        price_per_m2 = _calculator_value(raw, "BYN", "price_per_meter") or _number(value("square_meter"))
        improvements = labels.get("flat_building_improvements")
        if not improvements:
            improvements = value("flat_building_improvements")

        return cls(
            id=ad_id,
            title=str(raw.get("subject") or ""),
            url=str(raw.get("ad_link") or f"https://re.kufar.by/vi/{ad_id}"),
            category_id=str(value("category", "")),
            deal_type=str(value("type", "")),
            description=str(raw.get("body") or raw.get("body_short") or ""),
            address=str(value("address", "")),
            coordinates=normalized_coordinates,
            price_byn=price_byn,
            price_usd=price_usd,
            price_per_m2_byn=price_per_m2,
            rooms=str(value("rooms", "")),
            total_area=_number(value("size")),
            living_area=_number(value("size_living_space")),
            kitchen_area=_number(value("size_kitchen")),
            floor=_integer(value("floor")),
            floors=_integer(value("re_number_floors")),
            year_built=_integer(value("year_built")),
            wall_material=display("house_type"),
            condition=display("condition"),
            repair=display("flat_repair"),
            bathroom=display("bathroom"),
            balcony=display("balcony"),
            improvements=_as_text_list(improvements),
            seller_name=str(value("name", "")),
            contact_person=str(value("contact_person", "")),
            is_company=bool(raw.get("company_ad")),
            created_at=str(raw.get("created_at") or ""),
            listed_at=str(raw.get("list_time") or ""),
            images=_images(raw),
            phone_hidden=bool(raw.get("phone_hidden")),
            parameters=values,
            parameter_labels=labels,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.coordinates is not None:
            data["coordinates"] = list(self.coordinates)
        return data


@dataclass(slots=True)
class PaginationLink:
    label: str
    page: int
    token: str | None


@dataclass(slots=True)
class SearchPage:
    total: int
    listings: list[Listing]
    pagination: list[PaginationLink]

    @property
    def next_cursor(self) -> str | None:
        return next((item.token for item in self.pagination if item.label == "next"), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "count": len(self.listings),
            "next_cursor": self.next_cursor,
            "pagination": [asdict(item) for item in self.pagination],
            "listings": [item.to_dict() for item in self.listings],
        }


@dataclass(slots=True)
class MarketStats:
    total: int
    priced_count: int
    median_price_byn: float | None
    median_price_usd: float | None
    median_price_eur: float | None

    @classmethod
    def from_raw(cls, count: dict[str, Any], median: dict[str, Any]) -> MarketStats:
        return cls(
            total=int(count.get("count") or 0),
            priced_count=int(median.get("count") or 0),
            median_price_byn=_minor_units(median.get("median_price_byn")),
            median_price_usd=_minor_units(median.get("median_price_usd")),
            median_price_eur=_minor_units(median.get("median_price_eur")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Suggestion:
    text: str
    label: str
    kind: str
    preferred_category: str = ""

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Suggestion:
        return cls(
            text=str(raw.get("text") or ""),
            label=str(raw.get("label") or ""),
            kind=str(raw.get("type") or ""),
            preferred_category=str(raw.get("preferred_category") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MapListing:
    id: str
    list_id: str
    coordinates: tuple[float, float]
    price_byn: float | None
    flag_r: bool
    flag_v: bool

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> MapListing:
        coordinates = raw.get("c") or []
        if not isinstance(coordinates, list) or len(coordinates) != 2:
            coordinates = [0, 0]
        return cls(
            id=str(raw.get("i") or ""),
            list_id=str(raw.get("li") or raw.get("i") or ""),
            coordinates=(float(coordinates[0]), float(coordinates[1])),
            price_byn=_minor_units(raw.get("p")),
            flag_r=bool(raw.get("r")),
            flag_v=bool(raw.get("v")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["coordinates"] = list(self.coordinates)
        return data


@dataclass(slots=True)
class MapPage:
    total: int
    listings: list[MapListing]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "count": len(self.listings),
            "listings": [item.to_dict() for item in self.listings],
        }


def flatten_categories(categories: Iterable[Category]) -> list[Category]:
    result: list[Category] = []
    for category in categories:
        result.append(category)
        result.extend(flatten_categories(category.children))
    return result
