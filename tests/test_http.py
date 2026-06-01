"""공통 HTTP 동사 + 에러 매핑 검증 (httpx.MockTransport, 네트워크 없음)."""

import httpx
import pytest

from arcsolve.http import (
    UpstreamError,
    delete_json,
    get_json,
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


async def test_4xx_raises_upstream_error_with_payload():
    async def handler(req):
        return httpx.Response(401, json={"code": -401, "msg": "bad"})

    with pytest.raises(UpstreamError) as ei:
        await get_json("https://x", transport=_t(handler))
    assert ei.value.status == 401
    assert ei.value.payload["code"] == -401
