"""Notion 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·토큰 누락 확인.

get_json/post_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다.
인증은 헤더(Authorization: Bearer + Notion-Version)로 들어가는지 확인한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.notion.tools import register

MOD = "arcsolve.services.notion.tools"


@pytest.fixture
def tools(monkeypatch, load_tools):
    """NOTION_TOKEN이 설정된 기본 환경."""
    monkeypatch.setenv("NOTION_TOKEN", "secret-token")
    return load_tools(register)


# ─── 토큰 누락 ──────────────────────────────────────────────


async def test_all_tools_require_token(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    t = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    monkeypatch.setattr(f"{MOD}.post_json", http)

    out = await t["notion_search"](query="x")
    assert "NOTION_TOKEN" in out
    assert not http.calls  # HTTP 호출 전에 막힘

    out2 = await t["notion_get_page"](page_id="p")
    assert "NOTION_TOKEN" in out2
    assert not http.calls


# ─── search ─────────────────────────────────────────────────


async def test_search_request_headers_and_body(tools, monkeypatch, recording_http):
    body = {
        "object": "list",
        "results": [
            {
                "object": "page",
                "id": "pg1",
                "properties": {"제목": {"type": "title", "title": [{"plain_text": "내 페이지"}]}},
            },
            {"object": "data_source", "id": "ds1", "title": [{"plain_text": "Tasks"}]},
        ],
        "has_more": False,
        "next_cursor": None,
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.post_json", http)

    out = await tools["notion_search"](query="내", filter_type="page", page_size=10)
    assert http.last["url"] == "https://api.notion.com/v1/search"
    # 인증/버전은 헤더로 들어간다.
    assert http.last["headers"]["Authorization"] == "Bearer secret-token"
    assert http.last["headers"]["Notion-Version"] == "2026-03-11"
    # filter는 object 한정 객체.
    assert http.last["json"]["filter"] == {"value": "page", "property": "object"}
    assert http.last["json"]["query"] == "내"
    assert http.last["json"]["page_size"] == 10
    # 출력에 page 제목(properties 스캔)과 data_source 제목(최상위 title) 둘 다.
    assert "[page] pg1 — 내 페이지" in out
    assert "[data_source] ds1 — Tasks" in out


async def test_search_no_network_when_page_size_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tools["notion_search"](page_size=101)
    assert "page_size" in out and "100" in out  # 계약 위반은 HTTP 전에 막힘
    assert not http.calls


async def test_search_no_network_when_filter_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tools["notion_search"](filter_type="database")
    assert "filter_type" in out
    assert not http.calls


async def test_search_pagination_note(tools, monkeypatch, recording_http):
    body = {
        "object": "list",
        "results": [{"object": "page", "id": "p", "properties": {}}],
        "has_more": True,
        "next_cursor": "CUR123",
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tools["notion_search"](query="x")
    assert "다음 페이지 있음" in out and "CUR123" in out


async def test_search_empty(tools, monkeypatch, recording_http):
    http = recording_http(ret={"object": "list", "results": [], "has_more": False})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tools["notion_search"](query="none")
    assert "검색 결과 없음" in out


# ─── get_page ───────────────────────────────────────────────


async def test_get_page_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "object": "page",
        "id": "pg9",
        "url": "https://notion.so/pg9",
        "in_trash": False,
        "last_edited_time": "2026-06-01T10:00:00.000Z",
        "properties": {"Name": {"type": "title", "title": [{"plain_text": "회의록"}]}},
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["notion_get_page"](page_id="pg9")
    assert http.last["url"] == "https://api.notion.com/v1/pages/pg9"
    assert http.last["headers"]["Notion-Version"] == "2026-03-11"
    assert "회의록" in out
    assert "pg9" in out
    assert "https://notion.so/pg9" in out


# ─── get_block_children ─────────────────────────────────────


async def test_get_block_children_params_and_output(tools, monkeypatch, recording_http):
    body = {
        "object": "list",
        "results": [
            {
                "object": "block",
                "id": "b1",
                "type": "paragraph",
                "has_children": False,
                "paragraph": {"rich_text": [{"plain_text": "첫 문단"}]},
            },
            {
                "object": "block",
                "id": "b2",
                "type": "heading_1",
                "has_children": True,
                "heading_1": {"rich_text": [{"plain_text": "제목1"}]},
            },
            {"object": "block", "id": "b3", "type": "divider", "has_children": False, "divider": {}},
        ],
        "has_more": False,
        "next_cursor": None,
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["notion_get_block_children"](block_id="pg9", page_size=50)
    assert http.last["url"] == "https://api.notion.com/v1/blocks/pg9/children"
    # blocks children 페이지네이션은 쿼리 파라미터.
    assert http.last["params"]["page_size"] == 50
    assert "[paragraph] 첫 문단" in out
    assert "[heading_1] ⤵ 제목1" in out  # has_children 표시
    assert "[divider]" in out  # 본문 없는 블록도 표시


async def test_get_block_children_page_size_guard(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["notion_get_block_children"](block_id="b", page_size=200)
    assert "page_size" in out
    assert not http.calls


# ─── get_database ───────────────────────────────────────────


async def test_get_database_lists_data_sources(tools, monkeypatch, recording_http):
    body = {
        "object": "database",
        "id": "db1",
        "title": [{"plain_text": "프로젝트 DB"}],
        "data_sources": [
            {"id": "ds1", "name": "Default"},
            {"id": "ds2", "name": "Archive"},
        ],
        "in_trash": False,
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["notion_get_database"](database_id="db1")
    assert http.last["url"] == "https://api.notion.com/v1/databases/db1"
    assert "프로젝트 DB" in out
    assert "ds1 — Default" in out
    assert "ds2 — Archive" in out


# ─── get_data_source ────────────────────────────────────────


async def test_get_data_source_lists_property_schema(tools, monkeypatch, recording_http):
    body = {
        "object": "data_source",
        "id": "ds1",
        "title": [{"plain_text": "Tasks"}],
        "properties": {
            "Name": {"id": "title", "name": "Name", "type": "title"},
            "Status": {"id": "abc", "name": "Status", "type": "status"},
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["notion_get_data_source"](data_source_id="ds1")
    assert http.last["url"] == "https://api.notion.com/v1/data_sources/ds1"
    assert "Tasks" in out
    assert "Name: title" in out
    assert "Status: status" in out


# ─── query_data_source ──────────────────────────────────────


async def test_query_data_source_request_body_and_output(tools, monkeypatch, recording_http):
    body = {
        "object": "list",
        "results": [
            {"object": "page", "id": "r1", "properties": {"N": {"type": "title", "title": [{"plain_text": "행1"}]}}},
        ],
        "has_more": True,
        "next_cursor": "NEXT",
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.post_json", http)

    flt = {"property": "Status", "status": {"equals": "Done"}}
    out = await tools["notion_query_data_source"](data_source_id="ds1", filter=flt, page_size=5)
    assert http.last["url"] == "https://api.notion.com/v1/data_sources/ds1/query"
    assert http.last["headers"]["Authorization"] == "Bearer secret-token"
    assert http.last["json"]["filter"] == flt  # DSL pass-through
    assert http.last["json"]["page_size"] == 5
    assert "r1 — 행1" in out
    assert "다음 페이지 있음" in out and "NEXT" in out


async def test_query_data_source_empty(tools, monkeypatch, recording_http):
    http = recording_http(ret={"object": "list", "results": [], "has_more": False})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tools["notion_query_data_source"](data_source_id="ds1")
    assert "행 없음" in out


# ─── 에러 매핑 ──────────────────────────────────────────────


async def test_maps_401_invalid_token(tools, monkeypatch, recording_http):
    http = recording_http(
        exc=UpstreamError(401, {"object": "error", "status": 401, "code": "unauthorized", "message": "API token is invalid."})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["notion_get_page"](page_id="p")
    assert "401" in out and "NOTION_TOKEN" in out
    assert "unauthorized" in out  # code 노출


async def test_maps_404_not_shared(tools, monkeypatch, recording_http):
    http = recording_http(
        exc=UpstreamError(404, {"object": "error", "status": 404, "code": "object_not_found", "message": "Could not find page."})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["notion_get_page"](page_id="p")
    assert "404" in out and "공유" in out  # 통합 미공유 안내


async def test_maps_400_validation(tools, monkeypatch, recording_http):
    http = recording_http(
        exc=UpstreamError(400, {"object": "error", "status": 400, "code": "validation_error", "message": "body failed validation"})
    )
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tools["notion_search"](query="x")
    assert "400" in out


async def test_maps_429_rate_limit(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(429, {"object": "error", "status": 429, "code": "rate_limited", "message": "slow down"}))
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tools["notion_search"](query="x")
    assert "429" in out and "한도" in out


async def test_404_does_not_leak_non_dict_body(tools, monkeypatch, recording_http):
    # 본문이 비-dict(HTML 등)면 원문을 노출하지 않는다.
    http = recording_http(exc=UpstreamError(404, "<!doctype html><title>404</title>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["notion_get_page"](page_id="p")
    assert "404" in out
    assert "doctype" not in out
