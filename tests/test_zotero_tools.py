"""Zotero 도구 런타임 기능 검증 — 네트워크 없이 백엔드 해석·요청 조립·응답 파싱·에러 매핑 확인.

get_with_headers는 (본문, 헤더) 튜플을 돌려주므로 RecordingHTTP의 ret도 튜플로 준다.
"""

import httpx
import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.zotero.tools import register

MOD = "arcsolve.services.zotero.tools"


@pytest.fixture
def zt(monkeypatch, load_tools):
    """web 백엔드 기본 설정(API 키 + userID). source/group은 비워 auto=web가 되게 한다."""
    monkeypatch.delenv("ZOTERO_SOURCE", raising=False)
    monkeypatch.delenv("ZOTERO_GROUP_ID", raising=False)
    monkeypatch.setenv("ZOTERO_API_KEY", "K")
    monkeypatch.setenv("ZOTERO_USER_ID", "42")
    return load_tools(register)


async def test_search_web_request_and_output(zt, monkeypatch, recording_http):
    item = {"key": "ITM1", "version": 5, "data": {"itemType": "book", "title": "My Title"}}
    http = recording_http(ret=([item], {"total-results": "1"}))
    monkeypatch.setattr(f"{MOD}.get_with_headers", http)

    out = await zt["zotero_search_items"](q="cancer")
    assert http.last["url"] == "https://api.zotero.org/users/42/items"
    # 인증·버전 헤더가 정확히 주입된다(web).
    assert http.last["headers"] == {"Zotero-API-Version": "3", "Zotero-API-Key": "K"}
    assert http.last["params"]["q"] == "cancer"
    assert http.last["params"]["limit"] == 25
    assert "총 1건" in out
    assert "ITM1" in out and "My Title" in out


async def test_web_requires_user_or_group(monkeypatch, load_tools):
    monkeypatch.setenv("ZOTERO_SOURCE", "web")
    monkeypatch.setenv("ZOTERO_API_KEY", "K")
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    monkeypatch.delenv("ZOTERO_GROUP_ID", raising=False)
    tools = load_tools(register)
    out = await tools["zotero_search_items"]()
    assert "ZOTERO_USER_ID" in out  # 백엔드 설정 미흡 안내


async def test_local_backend_uses_users0_and_no_auth(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("ZOTERO_SOURCE", "local")
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret=([], {}))
    monkeypatch.setattr(f"{MOD}.get_with_headers", http)

    await tools["zotero_search_items"]()
    assert http.last["url"].startswith("http://localhost:23119/api/users/0/items")
    # 로컬은 무인증 — API 키 헤더가 없어야 한다.
    assert http.last["headers"] == {"Zotero-API-Version": "3"}


async def test_local_backend_supports_group_prefix(monkeypatch, load_tools, recording_http):
    # 로컬도 그룹 라이브러리(groups/<id>)를 지원한다(server_localAPI.js 라우트).
    monkeypatch.setenv("ZOTERO_SOURCE", "local")
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    monkeypatch.setenv("ZOTERO_GROUP_ID", "999")
    tools = load_tools(register)
    http = recording_http(ret=([], {}))
    monkeypatch.setattr(f"{MOD}.get_with_headers", http)

    await tools["zotero_search_items"]()
    assert http.last["url"].startswith("http://localhost:23119/api/groups/999/items")
    assert http.last["headers"] == {"Zotero-API-Version": "3"}  # 로컬은 무인증


async def test_get_item_parse(zt, monkeypatch, recording_http):
    item = {"key": "ABC", "version": 9, "data": {"itemType": "journalArticle", "title": "Paper"}}
    http = recording_http(ret=item)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await zt["zotero_get_item"](item_key="ABC")
    assert http.last["url"].endswith("/users/42/items/ABC")
    assert "ABC" in out and "Paper" in out


async def test_limit_over_max_rejected_before_http(zt, monkeypatch, recording_http):
    http = recording_http(ret=([], {}))
    monkeypatch.setattr(f"{MOD}.get_with_headers", http)
    out = await zt["zotero_search_items"](limit=101)
    assert "limit" in out and "100" in out  # 계약(1..100) 위반은 HTTP 전에 막힘
    assert not http.calls


async def test_maps_403_web(zt, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, {"message": "Forbidden"}))
    monkeypatch.setattr(f"{MOD}.get_with_headers", http)
    out = await zt["zotero_search_items"](q="x")
    assert "API 키" in out  # web 403 안내


async def test_fulltext_pdf_meta(zt, monkeypatch, recording_http):
    http = recording_http(ret={"content": "hello world", "indexedPages": 3, "totalPages": 10})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await zt["zotero_get_fulltext"](item_key="ATT1")
    assert http.last["url"].endswith("/users/42/items/ATT1/fulltext")
    assert "PDF 3/10" in out
    assert "hello world" in out


async def test_local_connect_error_message(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("ZOTERO_SOURCE", "local")
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(exc=httpx.ConnectError("connection refused"))
    monkeypatch.setattr(f"{MOD}.get_with_headers", http)
    out = await tools["zotero_search_items"]()
    assert "연결 실패" in out  # 로컬 앱 미실행/포트 안내
