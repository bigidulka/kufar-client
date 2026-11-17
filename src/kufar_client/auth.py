from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AuthStrategy(Protocol):
    def headers(self, method: str, url: str) -> dict[str, str]: ...

    def refresh(self) -> bool: ...


@dataclass(slots=True, frozen=True)
class NoAuth:
    """Kufar's public discovery endpoints require no application auth."""

    def headers(self, method: str, url: str) -> dict[str, str]:
        return {}

    def refresh(self) -> bool:
        return False
