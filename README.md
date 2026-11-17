# kufar-client

> Неофициальный reverse-engineered read-only клиент. Он не связан с Kufar и использует публичные web endpoints, которые вызывает фронтенд `re.kufar.by`. Условия использования и риск изменений API остаются на пользователе.

Python-библиотека и CLI для подбора жилья в Витебске: поиск с реальными фильтрами недвижимости, opaque cursor pagination, точная карточка, schema фильтров, медианные цены, подсказки и точки на карте. Клиент работает без браузера и принимает явный HTTP/SOCKS proxy.

## Быстрый запуск

```bash
cd ~/Projects/kufar-client
python3 -m venv .venv
.venv/bin/pip install -e .

export KUFAR_PROXY=http://127.0.0.1:8080
kufar search --rooms 2,3 --price-min 45000 --price-max 85000 \
  --area-min 45 --not-first-floor --not-last-floor --only-with-photo \
  --size 10 --json
```

`KUFAR_PROXY` читается явно. Стандартные `HTTP_PROXY`/`HTTPS_PROXY` transport игнорирует (`trust_env=False`), чтобы маршрут не менялся незаметно. Альтернативы: глобальный `--proxy URL` или `--no-proxy` перед именем команды.

## CLI

```bash
# Категории и живая taxonomy schema
kufar --proxy http://127.0.0.1:8080 categories недвиж --json
kufar --proxy http://127.0.0.1:8080 filters --category apartments --query rooms --json

# Квартиры Витебска, первая страница
kufar --proxy http://127.0.0.1:8080 search \
  --category apartments --rooms 2 --price-min 50000 --price-max 80000 \
  --area-min 50 --area-max 70 --sort price-asc --json

# Несколько страниц: CLI передаёт opaque cursor, а не числовой offset
kufar --proxy http://127.0.0.1:8080 search --rooms 2 --size 30 --pages 3 --jsonl

# Точная карточка, статистика, подсказки и карта
kufar --proxy http://127.0.0.1:8080 detail 1087626798 --json
kufar --proxy http://127.0.0.1:8080 stats --rooms 2 --area-min 50 --area-max 70 --json
kufar --proxy http://127.0.0.1:8080 suggest квартира --json
kufar --proxy http://127.0.0.1:8080 map --rooms 2 --size 500 --json
```

Категории: `apartments`, `houses`, `rooms`, `land`, `new-buildings`, `garages`, `commercial`, `estate`. Для редких полей можно передать исходное значение: `--filter 'fbi=v.and:1,6'`. Команда `filters` возвращает актуальные query names, enum IDs и ranges.

## Python

```python
import os
from kufar_client import KufarClient, SearchCriteria

criteria = SearchCriteria.vitebsk_apartments(
    rooms=("2", "3"),
    price_min=45_000,
    price_max=85_000,
    total_area_min=45,
    not_first_floor=True,
    not_last_floor=True,
)

with KufarClient(proxy=os.environ["KUFAR_PROXY"]) as client:
    page = client.search(criteria, size=10)
    stats = client.market_stats(criteria)
    full = client.detail(page.listings[0].id)
    print(page.total, stats.median_price_usd, full.address)
```

Полный пример: `examples/vitebsk_apartments.py`.

## Реализовано

| Метод | Назначение | Live |
|---|---|---|
| `categories()` | дерево категорий | да |
| `filters(criteria)` | category-specific taxonomy schema | да |
| `search()` / `iter_search()` | выдача и cursor pagination | да |
| `detail(id_or_url)` | точная полная карточка без text-search fallback | да |
| `market_stats()` | count и медиана BYN/USD/EUR | да |
| `suggestions()` | поисковые подсказки | да |
| `map_search()` | compact map points | да |

Полный каталог реализованных и найденных маршрутов находится в `endpoint_inventory.json`. Сырые цены API хранятся в сотых долях валюты; модели возвращают обычные BYN/USD/EUR. Диапазоны CLI задаются в обычных единицах выбранной валюты. Координаты модели: `[longitude, latitude]`.

## Auth и proxy

Публичные discovery endpoints классифицированы как **auth tier 0**. Bare HTTP replay через BY proxy вернул те же JSON shapes без cookies, bearer token и JS runtime. `X-Segmentation` содержит только публичные routing metadata (`web_re`, `web`, `ad_listing`/`ad_view`). Signer/HMAC не обнаружен.

Персональные account endpoints используют first-party session JWT/cookies и не входят в этот клиент.

## Rate limit

Замер 2026-10-03 на `rendered-paginated?size=1` через BY proxy:

- 10 последовательных запросов: 10 x `200`, median 173 ms, max 189 ms.
- Burst 20 запросов с concurrency 20: 20 x `200`, median 204 ms, max 226 ms.
- `429`, `Retry-After` и rate-limit headers не наблюдались.

Это короткая выборка, не гарантия лимита. Default остаётся консервативным: один запрос каждые `0.5 s` на экземпляр клиента. При первом `429` клиент сразу поднимает `RateLimitError` и не повторяет запрос. Детали: `rate_limit_measurement.json`.

## Проверка

```bash
PYTHONPATH=src pytest tests/test_unit.py
KUFAR_LIVE=1 KUFAR_PROXY=http://127.0.0.1:8080 \
  PYTHONPATH=src pytest tests/test_live.py
```

На 2026-10-03: unit `5 passed`, live `7 passed`; отдельно live-проверены все CLI-команды.

## Ограничения

- Телефон, captcha-вариант телефона и auth/account функции только каталогизированы; они не вызывались и не реализованы до подтверждения session/captcha contract.
- VIN относится к автомобилям и не входит в real-estate scope.
- Mutating endpoints намеренно отсутствуют: клиент read-only.
- Managed browser capture был недоступен из-за уже занятого CDP-порта. Endpoint catalog получен статическим анализом 62 frontend bundles и подтверждён отдельными bare HTTP replay для всех реализованных методов.
- Frontend и неофициальные endpoints могут измениться без предупреждения.
