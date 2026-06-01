"""모든 서비스가 공유하는 HTTP 호출 + 에러 매핑.

서비스는 여기 동사(post_form / get_json / post_json)를 재사용하고, 직접 httpx 세션을
만들지 않는다. 새 인증 방식(Bearer/API-key 등)은 헤더로 주입한다.
"""

from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = 10.0


class UpstreamError(RuntimeError):
    """상류 API가 4xx/5xx를 반환했을 때. payload에 원본 응답(JSON 또는 text)을 담는다."""

    def __init__(self, status: int, payload: dict | str):
        self.status = status
        self.payload = payload
        super().__init__(f"upstream {status}: {payload}")


def bearer(token: str) -> dict[str, str]:
    """Bearer 인증 헤더."""
    return {"Authorization": f"Bearer {token}"}


async def _request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        r = await client.request(method, url, headers=headers, params=params, data=data, json=json)
    if r.status_code >= 400:
        try:
            payload: dict | str = r.json()
        except Exception:
            payload = r.text
        raise UpstreamError(r.status_code, payload)
    if not r.content:
        return {}
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


async def post_form(
    url: str,
    *,
    token: str | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """application/x-www-form-urlencoded POST. token을 주면 Bearer 헤더를 붙인다."""
    h = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    if token:
        h.update(bearer(token))
    if headers:
        h.update(headers)
    return await _request("POST", url, headers=h, data=data, timeout=timeout, transport=transport)


async def get_json(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """GET → JSON."""
    return await _request(
        "GET", url, headers=headers, params=params, timeout=timeout, transport=transport
    )


async def post_json(
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """application/json POST → JSON."""
    return await _request(
        "POST", url, headers=headers, json=json, timeout=timeout, transport=transport
    )
