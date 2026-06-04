"""모든 서비스가 공유하는 HTTP 호출 + 에러 매핑.

서비스는 여기 동사(post_form / get_json / get_text / get_with_headers / post_json /
patch_json / delete_json / post_multipart)를 재사용하고, 직접 httpx 세션을 만들지 않는다.
새 인증 방식(Bearer/API-key 등)은 헤더로 주입한다.
"""

from __future__ import annotations

import re

import httpx

from arcsolve import __version__

DEFAULT_TIMEOUT = 10.0

# 식별용 기본 User-Agent. UA 누락 시 403을 주는 API(NWS·Wikipedia 등)를 구조적으로 예방하고,
# 서비스마다 UA 문자열을 손으로 박는 drift를 없앤다. 호출자가 명시한 UA가 항상 우선한다.
DEFAULT_USER_AGENT = f"arcsolve/{__version__} (+https://github.com/ArcSolver/ArcSolve-Kit)"


def _with_default_ua(headers: dict | None) -> dict:
    """기본 User-Agent를 깔고 호출자 헤더로 덮어쓴다(호출자 UA가 우선)."""
    merged = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        merged.update(headers)
    return merged


class UpstreamError(RuntimeError):
    """상류 API가 4xx/5xx를 반환했을 때. payload에 원본 응답(JSON 또는 text)을 담는다."""

    def __init__(self, status: int, payload: dict | str):
        self.status = status
        self.payload = payload
        super().__init__(f"upstream {status}: {payload}")


def bearer(token: str) -> dict[str, str]:
    """Bearer 인증 헤더."""
    return {"Authorization": f"Bearer {token}"}


async def _request_raw(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
    files: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> tuple[dict | list, dict[str, str]]:
    """공통 호출. (JSON 본문, 응답 헤더 dict) 튜플 반환. 4xx/5xx면 UpstreamError.

    헤더 dict의 키는 httpx가 소문자로 정규화한다(예: "total-results", "link").
    """
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        r = await client.request(
            method, url, headers=_with_default_ua(headers),
            params=params, data=data, json=json, files=files,
        )
    if r.status_code >= 400:
        try:
            payload: dict | str = r.json()
        except Exception:
            payload = r.text
        raise UpstreamError(r.status_code, payload)
    resp_headers = dict(r.headers)
    if not r.content:
        return {}, resp_headers
    try:
        return r.json(), resp_headers
    except Exception:
        return {"raw": r.text}, resp_headers


async def _request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
    files: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    body, _ = await _request_raw(
        method,
        url,
        headers=headers,
        params=params,
        data=data,
        json=json,
        files=files,
        timeout=timeout,
        transport=transport,
    )
    return body


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


async def get_text(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """GET → 응답 본문을 **raw `str`로** 반환(JSON 파싱 안 함).

    JSON이 아닌 본문을 주는 API(예: arXiv의 Atom 1.0 XML)에서 사용한다. 서비스가 본문을
    표준 라이브러리(`xml.etree.ElementTree` 등)로 직접 파싱한다. 4xx/5xx 에러 매핑은
    `get_json`과 동일(UpstreamError, payload는 JSON이면 dict, 아니면 text). 본문이 비어 있으면
    빈 문자열을 돌려준다. transport 주입으로 네트워크 없이 테스트할 수 있다.
    """
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        r = await client.request("GET", url, headers=_with_default_ua(headers), params=params)
    if r.status_code >= 400:
        try:
            payload: dict | str = r.json()
        except Exception:
            payload = r.text
        raise UpstreamError(r.status_code, payload)
    return r.text


async def get_with_headers(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> tuple[dict | list, dict[str, str]]:
    """GET → (JSON 본문, 응답 헤더 dict).

    페이지네이션/버전/백오프가 **본문이 아니라 응답 헤더**에 실리는 API(예: Zotero의
    `Total-Results`/`Link`/`Last-Modified-Version`/`Backoff`)에서 사용한다. 헤더 키는 소문자.
    """
    return await _request_raw(
        "GET", url, headers=headers, params=params, timeout=timeout, transport=transport
    )


_LINK_RE = re.compile(r'<([^>]*)>\s*;\s*rel="?([^",;]+)"?')


def parse_link_header(value: str | None) -> dict[str, str]:
    """RFC 5988 `Link` 헤더를 {rel: url} 로 파싱한다(예: 다음 페이지 `next`).

    URL 안에 콤마(쿼리 파라미터 등)가 있어도 `<...>` 경계로 안전하게 분리한다. 값이 없으면 {}.
    """
    result: dict[str, str] = {}
    if not value:
        return result
    for m in _LINK_RE.finditer(value):
        result[m.group(2).strip()] = m.group(1).strip()
    return result


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


MULTIPART_TIMEOUT = 30.0


async def post_multipart(
    url: str,
    *,
    data: dict | None = None,
    files: dict | None = None,
    headers: dict | None = None,
    timeout: float = MULTIPART_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """multipart/form-data POST → JSON. (로컬 파일 업로드)

    `files`는 httpx 형식: {"<필드명>": (파일명, 바이트/파일객체, MIME)}.
    `data`는 함께 보낼 폼 필드(문자열 값). Content-Type/boundary는 httpx가 자동 설정하므로
    직접 지정하지 않는다. 업로드는 느릴 수 있어 기본 timeout을 늘렸다.
    """
    return await _request(
        "POST", url, headers=headers, data=data, files=files, timeout=timeout, transport=transport
    )


async def patch_json(
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """application/json PATCH → JSON. (리소스 부분 수정, 예: 메시지 편집)"""
    return await _request(
        "PATCH", url, headers=headers, json=json, timeout=timeout, transport=transport
    )


async def delete_json(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """DELETE → JSON(또는 본문 없으면 빈 dict). (리소스 삭제, 예: 메시지 삭제)"""
    return await _request(
        "DELETE", url, headers=headers, params=params, timeout=timeout, transport=transport
    )
