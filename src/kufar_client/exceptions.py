from __future__ import annotations

from typing import Any


class KufarError(Exception):
    """Base client error."""


class TransportError(KufarError):
    pass


class ApiError(KufarError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        url: str | None = None,
        payload: Any = None,
    ) -> None:
        self.status = status
        self.url = url
        self.payload = payload
        super().__init__(message)


class RateLimitError(ApiError):
    def __init__(self, message: str, *, retry_after: str | None, **kwargs: Any) -> None:
        self.retry_after = retry_after
        super().__init__(message, **kwargs)


class ParseError(KufarError):
    pass


class NotFoundError(KufarError):
    pass
