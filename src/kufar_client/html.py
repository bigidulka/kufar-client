from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Any

from .exceptions import ParseError


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.capture = dict(attrs).get("id") == "__NEXT_DATA__"

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.capture = False


def extract_next_data(html: str) -> dict[str, Any]:
    parser = _NextDataParser()
    parser.feed(html)
    raw = "".join(parser.parts).strip()
    if not raw:
        raise ParseError("Kufar page does not contain __NEXT_DATA__")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid Kufar __NEXT_DATA__: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("Kufar __NEXT_DATA__ is not an object")
    return data


def initial_state(html: str) -> dict[str, Any]:
    data = extract_next_data(html)
    try:
        state = data["props"]["initialState"]
    except (KeyError, TypeError) as exc:
        raise ParseError("Kufar page has no props.initialState") from exc
    if not isinstance(state, dict):
        raise ParseError("Kufar initialState is not an object")
    return state
