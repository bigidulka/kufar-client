from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CATEGORY_IDS = {
    "estate": "1000",
    "new-buildings": "1120",
    "apartments": "1010",
    "rooms": "1040",
    "houses": "1020",
    "garages": "1030",
    "land": "1080",
    "commercial": "1050",
}

SORTS = {
    "date": "lst.d",
    "price-asc": "prc.a",
    "price-desc": "prc.d",
}


def _range(lower: float | None, upper: float | None) -> str | None:
    if lower is None and upper is None:
        return None
    left = "" if lower is None else str(lower)
    right = "" if upper is None else str(upper)
    return f"r:{left},{right}"


def _selection(values: tuple[str | int, ...] | list[str | int], mode: str = "or") -> str | None:
    clean = [str(value).strip() for value in values if str(value).strip()]
    return f"v.{mode}:{','.join(clean)}" if clean else None


@dataclass(slots=True)
class SearchCriteria:
    category: str = "1010"
    deal_type: str = "sell"
    region: str = "6"
    area: str = "18"
    query: str = ""
    sort: str = "date"
    price_currency: str = "USD"
    price_min: float | None = None
    price_max: float | None = None
    rooms: tuple[str, ...] = ()
    total_area_min: float | None = None
    total_area_max: float | None = None
    living_area_min: float | None = None
    living_area_max: float | None = None
    kitchen_area_min: float | None = None
    kitchen_area_max: float | None = None
    floor_min: int | None = None
    floor_max: int | None = None
    floors_min: int | None = None
    floors_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    wall_materials: tuple[str, ...] = ()
    repairs: tuple[str, ...] = ()
    condition: str = ""
    improvements: tuple[str, ...] = ()
    not_first_floor: bool = False
    not_last_floor: bool = False
    new_building: bool = False
    company_only: bool = False
    only_with_photo: bool = False
    extra: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.category = CATEGORY_IDS.get(self.category, self.category)
        normalized_currency = self.price_currency.upper()
        self.price_currency = "BYR" if normalized_currency == "BYN" else normalized_currency
        if self.price_currency not in {"USD", "BYR"}:
            raise ValueError("price_currency must be USD, BYN, or BYR")
        if self.sort not in SORTS and self.sort not in SORTS.values():
            raise ValueError(f"unsupported sort: {self.sort}")

    def to_params(self, *, size: int = 30, cursor: str | None = None) -> list[tuple[str, str]]:
        if not 1 <= size <= 1000:
            raise ValueError("size must be between 1 and 1000")
        params: list[tuple[str, str]] = [
            ("size", str(size)),
            ("lang", "ru"),
            ("ot", "1"),
            ("cat", self.category),
            ("typ", self.deal_type),
            ("rgn", self.region),
            ("ar", self.area),
            ("sort", SORTS.get(self.sort, self.sort)),
        ]
        if cursor:
            params.append(("cursor", cursor))
        if self.query:
            params.append(("query", self.query))

        filters: dict[str, str | None] = {
            "prc": _range(self.price_min, self.price_max),
            "rms": _selection(self.rooms),
            "st": _range(self.total_area_min, self.total_area_max),
            "sls": _range(self.living_area_min, self.living_area_max),
            "skt": _range(self.kitchen_area_min, self.kitchen_area_max),
            "fl": _range(self.floor_min, self.floor_max),
            "nmfl": _range(self.floors_min, self.floors_max),
            "yb": _range(self.year_min, self.year_max),
            "hst": _selection(self.wall_materials),
            "flrp": _selection(self.repairs),
            "cnd": _selection((self.condition,)) if self.condition else None,
            "fbi": _selection(self.improvements, "and"),
            "nff": "1" if self.not_first_floor else None,
            "nlf": "1" if self.not_last_floor else None,
            "nwbl": "1" if self.new_building else None,
            "cmp": "1" if self.company_only else None,
            "oph": "1" if self.only_with_photo else None,
        }
        if filters["prc"]:
            params.append(("cur", self.price_currency))
        params.extend((key, value) for key, value in filters.items() if value is not None)
        params.extend((str(key), str(value)) for key, value in self.extra.items())
        return params

    @classmethod
    def vitebsk_apartments(cls, **kwargs: Any) -> SearchCriteria:
        values: dict[str, Any] = {
            "category": "1010",
            "deal_type": "sell",
            "region": "6",
            "area": "18",
        }
        values.update(kwargs)
        return cls(**values)
