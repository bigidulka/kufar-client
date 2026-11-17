from __future__ import annotations

import json
import threading
import time
from typing import Any, Self
from urllib.parse import urljoin

from curl_cffi import requests

from .auth import AuthStrategy, NoAuth
from .exceptions import ApiError, RateLimitError, TransportError


class Transport:
    def __init__(
        self,
        base_url: str,
        *,
        proxy: str | None = None,
        timeout: float = 30.0,
        min_interval: float = 0.5,
        retries: int = 3,
        impersonate: str = "chrome",
        auth: AuthStrategy | None = None,
    ) -> None:
        if min_interval < 0:
            raise ValueError("min_interval cannot be negative")
        if retries < 1:
            raise ValueError("retries must be at least 1")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.min_interval = min_interval
        self.retries = retries
        self.auth = auth or NoAuth()
        self._lock = threading.Lock()
        self._last_request = 0.0
        proxies = {"http": proxy, "https": proxy} if proxy else {}
        self.session = requests.Session(
            impersonate=impersonate,
            proxies=proxies,
            trust_env=False,
        )

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def absolute_url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def _throttle(self) -> None:
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    @staticmethod
    def _error_payload(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:1000]

    def get(
        self,
        path: str,
        *,
        params: Any = None,
        accept: str = "application/json, */*;q=0.8",
        referer: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        url = self.absolute_url(path)
        auth_refreshed = False
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._throttle()
            headers = {
                "Accept": accept,
                "Accept-Language": "ru-BY,ru;q=0.9,be;q=0.8,en;q=0.7",
                **self.auth.headers("GET", url),
                **(extra_headers or {}),
            }
            if referer:
                headers["Referer"] = referer
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.errors.RequestsError as exc:
                last_error = TransportError(f"GET {url} failed: {exc}")
                if attempt + 1 < self.retries:
                    time.sleep(0.75 * (2**attempt))
                continue

            if response.status_code == 429:
                raise RateLimitError(
                    f"Kufar rate limited GET {url}",
                    status=429,
                    url=url,
                    payload=self._error_payload(response),
                    retry_after=response.headers.get("Retry-After"),
                )
            if response.status_code == 401 and not auth_refreshed and self.auth.refresh():
                auth_refreshed = True
                continue
            if response.status_code >= 500:
                last_error = ApiError(
                    f"Kufar returned HTTP {response.status_code} for GET {url}",
                    status=response.status_code,
                    url=url,
                    payload=self._error_payload(response),
                )
                if attempt + 1 < self.retries:
                    time.sleep(0.75 * (2**attempt))
                continue
            if response.status_code >= 400:
                raise ApiError(
                    f"Kufar returned HTTP {response.status_code} for GET {url}",
                    status=response.status_code,
                    url=url,
                    payload=self._error_payload(response),
                )
            return response
        raise last_error or TransportError(f"GET {url} failed after {self.retries} attempts")

    def get_json(self, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.get(path, **kwargs)
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ApiError(f"Kufar returned non-JSON response for {response.url}", url=response.url) from exc
        if not isinstance(payload, dict):
            raise ApiError(f"Kufar returned non-object JSON for {response.url}", url=response.url, payload=payload)
        return payload

    def get_text(self, path: str, **kwargs: Any) -> str:
        kwargs.setdefault("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        return self.get(path, **kwargs).text
