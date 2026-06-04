"""공통 HTTP 동사 + 에러 매핑 검증 (httpx.MockTransport, 네트워크 없음)."""

import httpx
import pytest

from arcsolve.http import (
    NetworkError,
    Retry,
    UpstreamError,
    assert_public_url,
    delete_json,
    get_json,
    get_text,
    get_with_headers,
    parse_link_header,
    patch_json,
    post_form,
    post_json,
    post_multipart,
)


def _t(handler):
    return httpx.MockTransport(handler)


async def test_get_json_ok():
    async def handler(req):
        assert req.method == "GET"
        return httpx.Response(200, json={"ok": True})

    assert await get_json("https://x/y", transport=_t(handler)) == {"ok": True}


async def test_get_text_returns_raw_body_without_json_parse():
    xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><id>x</id></feed>'

    async def handler(req):
        assert req.method == "GET"
        return httpx.Response(200, text=xml, headers={"content-type": "application/atom+xml"})

    out = await get_text("https://export.arxiv.org/api/query", transport=_t(handler))
    assert isinstance(out, str)
    assert out == xml  # JSON 파싱 없이 원문 그대로


async def test_get_text_passes_params_and_headers():
    seen = {}

    async def handler(req):
        seen["url"] = str(req.url)
        seen["ua"] = req.headers.get("user-agent")
        return httpx.Response(200, text="ok")

    await get_text(
        "https://x/api/query",
        params={"search_query": "all:electron", "max_results": 5},
        headers={"User-Agent": "arcsolve/arxiv"},
        transport=_t(handler),
    )
    assert "search_query=all%3Aelectron" in seen["url"]
    assert "max_results=5" in seen["url"]
    assert seen["ua"] == "arcsolve/arxiv"


async def test_get_text_empty_body_returns_empty_string():
    async def handler(req):
        return httpx.Response(200)

    assert await get_text("https://x", transport=_t(handler)) == ""


async def test_get_text_4xx_raises_upstream_error():
    async def handler(req):
        # arXiv: max_results>30000 → HTTP 400(본문은 text/plain 설명).
        return httpx.Response(400, text="max_results exceeded")

    with pytest.raises(UpstreamError) as ei:
        await get_text("https://x", transport=_t(handler))
    assert ei.value.status == 400
    assert ei.value.payload == "max_results exceeded"


async def test_post_form_sets_bearer_and_content_type():
    seen = {}

    async def handler(req):
        seen["auth"] = req.headers.get("authorization")
        seen["ct"] = req.headers.get("content-type")
        seen["body"] = req.content.decode()
        return httpx.Response(200, json={"result_code": 0})

    out = await post_form("https://x/y", token="T", data={"a": "b"}, transport=_t(handler))
    assert out == {"result_code": 0}
    assert seen["auth"] == "Bearer T"
    assert "application/x-www-form-urlencoded" in seen["ct"]
    assert "a=b" in seen["body"]


async def test_post_json_sends_json_body():
    async def handler(req):
        assert req.headers.get("content-type", "").startswith("application/json")
        return httpx.Response(201, json={"id": 1})

    assert await post_json("https://x", json={"k": "v"}, transport=_t(handler)) == {"id": 1}


async def test_patch_json_sends_patch_with_json_body():
    seen = {}

    async def handler(req):
        seen["method"] = req.method
        seen["body"] = req.content.decode()
        return httpx.Response(200, json={"id": "1", "content": "edited"})

    out = await patch_json("https://x/msg/1", json={"content": "edited"}, transport=_t(handler))
    assert out == {"id": "1", "content": "edited"}
    assert seen["method"] == "PATCH"
    assert "edited" in seen["body"]


async def test_delete_json_returns_empty_dict_on_no_content():
    async def handler(req):
        assert req.method == "DELETE"
        return httpx.Response(204)

    assert await delete_json("https://x/msg/1", transport=_t(handler)) == {}


async def test_post_multipart_sends_file_part_and_form_fields():
    seen = {}

    async def handler(req):
        seen["method"] = req.method
        seen["ct"] = req.headers.get("content-type", "")
        seen["body"] = req.content  # bytes
        return httpx.Response(200, json={"ok": True})

    out = await post_multipart(
        "https://x/upload",
        data={"chat_id": "42"},
        files={"photo": ("pic.jpg", b"\xff\xd8\xff binary", "image/jpeg")},
        transport=_t(handler),
    )
    assert out == {"ok": True}
    assert seen["method"] == "POST"
    assert seen["ct"].startswith("multipart/form-data")  # boundary는 httpx가 자동 설정
    assert b"binary" in seen["body"]          # 파일 파트 바이트 존재
    assert b'name="chat_id"' in seen["body"]  # 폼 필드 동시 존재
    assert b'name="photo"' in seen["body"]
    assert b"pic.jpg" in seen["body"]


async def test_get_with_headers_returns_body_and_headers():
    async def handler(req):
        return httpx.Response(
            200,
            json=[{"key": "AAA"}],
            headers={
                "Total-Results": "37",
                "Link": '<https://api.zotero.org/users/1/items?start=25>; rel="next"',
                "Last-Modified-Version": "1234",
            },
        )

    body, headers = await get_with_headers("https://api.zotero.org/x", transport=_t(handler))
    assert body == [{"key": "AAA"}]
    # 헤더 키는 소문자로 정규화된다.
    assert headers["total-results"] == "37"
    assert headers["last-modified-version"] == "1234"
    assert "rel=" in headers["link"]


def test_parse_link_header_extracts_rels():
    # URL 안에 콤마(itemKey 목록 등)가 있어도 <...> 경계로 안전 분리.
    value = (
        '<https://api.zotero.org/users/1/items?itemKey=A,B&start=25>; rel="next", '
        '<https://api.zotero.org/users/1/items?start=300>; rel="last"'
    )
    links = parse_link_header(value)
    assert links["next"] == "https://api.zotero.org/users/1/items?itemKey=A,B&start=25"
    assert links["last"] == "https://api.zotero.org/users/1/items?start=300"


def test_parse_link_header_empty():
    assert parse_link_header(None) == {}
    assert parse_link_header("") == {}


async def test_default_user_agent_applied_when_caller_omits():
    seen = {}

    async def handler(req):
        seen["ua"] = req.headers.get("user-agent")
        return httpx.Response(200, json={"ok": True})

    await get_json("https://x", transport=_t(handler))
    assert seen["ua"].startswith("arcsolve/")  # 코어 기본 UA 주입


async def test_caller_user_agent_overrides_default():
    seen = {}

    async def handler(req):
        seen["ua"] = req.headers.get("user-agent")
        return httpx.Response(200, json={"ok": True})

    # 서비스가 명시한 UA(예: NWS/Wikipedia 필수 UA)는 코어 기본값을 덮어쓴다.
    await get_json("https://x", headers={"User-Agent": "custom/1.0"}, transport=_t(handler))
    assert seen["ua"] == "custom/1.0"


async def test_4xx_raises_upstream_error_with_payload():
    async def handler(req):
        return httpx.Response(401, json={"code": -401, "msg": "bad"})

    with pytest.raises(UpstreamError) as ei:
        await get_json("https://x", transport=_t(handler))
    assert ei.value.status == 401
    assert ei.value.payload["code"] == -401


# ── opt-in 재시도/백오프 + 전송계층 에러분류 ──────────────────────────────────


async def test_retry_recovers_after_transient_503():
    calls = {"n": 0}

    async def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"ok": True})

    out = await get_json("https://x", transport=_t(handler), retry=Retry(attempts=2, backoff=0))
    assert out == {"ok": True}
    assert calls["n"] == 2  # 503 한 번 + 재시도 성공


async def test_retry_honors_retry_after_header():
    calls = {"n": 0}

    async def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"e": "rate"})
        return httpx.Response(200, json={"ok": True})

    # backoff=5초지만 Retry-After:0을 우선 존중 → 대기 없이 즉시 재시도(테스트가 빨리 끝남).
    out = await get_json("https://x", transport=_t(handler), retry=Retry(attempts=3, backoff=5))
    assert out == {"ok": True}
    assert calls["n"] == 2


async def test_retry_exhausted_raises_upstream_error():
    async def handler(req):
        return httpx.Response(503, text="always busy")

    with pytest.raises(UpstreamError) as ei:
        await get_json("https://x", transport=_t(handler), retry=Retry(attempts=1, backoff=0))
    assert ei.value.status == 503  # 재시도 소진 후 평소처럼 UpstreamError


async def test_transport_error_retried_then_raises_network_error():
    calls = {"n": 0}

    async def handler(req):
        calls["n"] += 1
        raise httpx.ConnectError("connection refused")

    with pytest.raises(NetworkError):
        await get_json("https://x", transport=_t(handler), retry=Retry(attempts=2, backoff=0))
    assert calls["n"] == 3  # 최초 1 + 재시도 2


async def test_no_retry_propagates_raw_httpx_error_by_default():
    async def handler(req):
        raise httpx.ConnectError("connection refused")

    # 기본(retry 미지정)은 원본 httpx 예외 그대로 — 기존 서비스의 `except httpx.ConnectError` 호환.
    with pytest.raises(httpx.ConnectError):
        await get_json("https://x", transport=_t(handler))


# ── 배포 전 하드닝: SSRF·DoS·정보노출 ────────────────────────────────────────


@pytest.mark.parametrize(
    "bad",
    [
        "http://127.0.0.1/x",
        "http://169.254.169.254/latest/meta-data/",  # 클라우드 메타데이터
        "http://10.0.0.5/x",
        "http://[::1]/x",
        "http://0.0.0.0/x",
    ],
)
async def test_assert_public_url_blocks_internal(bad):
    # 리터럴 IP는 DNS를 타지 않으므로 무네트워크로 검증된다.
    with pytest.raises(ValueError):
        await assert_public_url(bad)


async def test_assert_public_url_allows_public_literal():
    await assert_public_url("http://8.8.8.8/")  # 공인 IP → 통과(raise 없음)


async def test_assert_public_url_rejects_non_http():
    with pytest.raises(ValueError):
        await assert_public_url("file:///etc/passwd")


async def test_get_text_guard_ssrf_blocks_internal():
    with pytest.raises(ValueError):
        await get_text("http://127.0.0.1/feed", guard_ssrf=True)


async def test_network_error_masks_token_in_url():
    async def handler(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(NetworkError) as ei:
        await get_json(
            "https://api.telegram.org/bot123:SECRET/sendMessage",
            transport=_t(handler),
            retry=Retry(attempts=0, backoff=0),
        )
    msg = str(ei.value)
    assert "SECRET" not in msg and "bot123" not in msg  # 토큰 누출 없음
    assert "api.telegram.org" in msg  # 호스트는 진단용으로 유지


def test_upstream_error_truncates_long_text_payload():
    e = UpstreamError(500, "E" * 5000)
    assert len(e.payload) <= 2048 + 10
    assert e.payload.endswith("…(절단)")


def test_upstream_error_keeps_dict_payload():
    e = UpstreamError(400, {"code": -1, "msg": "x"})
    assert e.payload == {"code": -1, "msg": "x"}  # dict는 서비스가 파싱하므로 보존


async def test_retry_after_is_capped_to_max_delay():
    calls = {"n": 0}

    async def handler(req):
        calls["n"] += 1
        return httpx.Response(503, headers={"Retry-After": "999999"}, text="busy")

    # max_delay=0 → 거대 Retry-After여도 즉시 재시도(장시간 sleep 자기-DoS 방지). 빨리 끝나야 한다.
    with pytest.raises(UpstreamError):
        await get_json(
            "https://x", transport=_t(handler), retry=Retry(attempts=1, backoff=0, max_delay=0)
        )
    assert calls["n"] == 2


async def test_get_text_max_bytes_rejects_large_body():
    async def handler(req):
        return httpx.Response(200, text="A" * 5000)

    with pytest.raises(UpstreamError) as ei:
        await get_text("https://x", transport=_t(handler), max_bytes=1000)
    assert ei.value.status == 413


async def test_get_text_max_bytes_allows_small_body():
    async def handler(req):
        return httpx.Response(200, text="small")

    assert await get_text("https://x", transport=_t(handler), max_bytes=1000) == "small"
