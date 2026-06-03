"""Notion 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수(base·버전)·경로 빌더·page_size 검증·본문 빌더(search filter 객체·query
pass-through)·응답 모델 파싱·순수 헬퍼(rich_text→plain·page_title 타입 스캔·block 평문)·
에러 모델. HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.services.notion.contract import (
    BASE_URL,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
    NOTION_VERSION,
    SEARCH,
    Database,
    DataSource,
    ListResponse,
    NotionError,
    Page,
    block_plain_text,
    blocks_children_path,
    build_query_body,
    build_search_body,
    data_source_path,
    data_source_query_path,
    database_path,
    headers,
    page_params,
    page_path,
    page_title,
    rich_text_to_plain,
    validate_page_size,
    validate_search_filter,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://api.notion.com/v1"
    assert NOTION_VERSION == "2026-03-11"  # 최신 버전 핀 고정
    assert SEARCH == "/search"
    assert DEFAULT_PAGE_SIZE == 25
    assert MIN_PAGE_SIZE == 1
    assert MAX_PAGE_SIZE == 100


# ─── 경로 빌더 ──────────────────────────────────────────────


def test_path_builders():
    assert page_path("abc") == "/pages/abc"
    assert blocks_children_path("abc") == "/blocks/abc/children"
    assert database_path("db1") == "/databases/db1"
    assert data_source_path("ds1") == "/data_sources/ds1"
    assert data_source_query_path("ds1") == "/data_sources/ds1/query"


# ─── 헤더 ───────────────────────────────────────────────────


def test_headers_include_bearer_and_version():
    h = headers("SECRET")
    assert h["Authorization"] == "Bearer SECRET"
    assert h["Notion-Version"] == "2026-03-11"  # 필수 버전 헤더


# ─── page_size 검증 ─────────────────────────────────────────


def test_validate_page_size_bounds():
    assert validate_page_size(MIN_PAGE_SIZE) == 1
    assert validate_page_size(MAX_PAGE_SIZE) == 100
    with pytest.raises(ValueError):
        validate_page_size(0)
    with pytest.raises(ValueError):
        validate_page_size(MAX_PAGE_SIZE + 1)


def test_validate_search_filter():
    assert validate_search_filter("page") == "page"
    assert validate_search_filter("data_source") == "data_source"
    with pytest.raises(ValueError):
        validate_search_filter("database")  # 2025-09-03+ 에서 폐기된 값


# ─── 본문/파라미터 빌더 ─────────────────────────────────────


def test_build_search_body_omits_none():
    assert build_search_body() == {}


def test_build_search_body_filter_object_shape():
    body = build_search_body(query="docs", filter_type="data_source", page_size=10)
    assert body["query"] == "docs"
    # filter는 {"value": ..., "property": "object"} 객체여야 한다.
    assert body["filter"] == {"value": "data_source", "property": "object"}
    assert body["page_size"] == 10


def test_build_search_body_rejects_bad_filter_and_page_size():
    with pytest.raises(ValueError):
        build_search_body(filter_type="database")
    with pytest.raises(ValueError):
        build_search_body(page_size=MAX_PAGE_SIZE + 1)


def test_build_query_body_passes_through_filter_and_sorts():
    flt = {"property": "Status", "status": {"equals": "Done"}}
    srt = [{"property": "Name", "direction": "ascending"}]
    body = build_query_body(filter=flt, sorts=srt, page_size=5, start_cursor="cur")
    assert body["filter"] == flt  # DSL 그대로 전달
    assert body["sorts"] == srt
    assert body["page_size"] == 5
    assert body["start_cursor"] == "cur"


def test_build_query_body_omits_none():
    assert build_query_body() == {}


def test_page_params():
    assert page_params() == {}
    p = page_params(page_size=10, start_cursor="c")
    assert p["page_size"] == 10
    assert p["start_cursor"] == "c"
    with pytest.raises(ValueError):
        page_params(page_size=MAX_PAGE_SIZE + 1)


# ─── 순수 헬퍼 ──────────────────────────────────────────────


def test_rich_text_to_plain():
    assert rich_text_to_plain(None) == ""
    assert rich_text_to_plain([]) == ""
    items = [{"plain_text": "Hello "}, {"plain_text": "world"}]
    assert rich_text_to_plain(items) == "Hello world"


def test_page_title_scans_title_type_property():
    # 제목 프로퍼티 이름은 고정이 아님 — type=="title"을 스캔해야 한다.
    props = {
        "Name": {"type": "rich_text", "rich_text": [{"plain_text": "not title"}]},
        "제목": {"type": "title", "title": [{"plain_text": "실제 제목"}]},
    }
    assert page_title(props) == "실제 제목"


def test_page_title_fallback_when_absent():
    assert page_title({}) == "(제목 없음)"
    assert page_title(None) == "(제목 없음)"


def test_block_plain_text_reads_typed_rich_text():
    block = {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": "본문"}], "color": "default"},
    }
    assert block_plain_text(block) == "본문"


def test_block_plain_text_empty_for_non_text_block():
    # rich_text가 없는 블록(divider 등)은 "".
    assert block_plain_text({"type": "divider", "divider": {}}) == ""
    assert block_plain_text({}) == ""


# ─── 응답 모델 ──────────────────────────────────────────────


def test_list_response_envelope():
    lr = ListResponse.model_validate(
        {
            "object": "list",
            "results": [{"id": "p1"}],
            "next_cursor": "cur",
            "has_more": True,
            "type": "page_or_data_source",
            "extra": "ign",
        }
    )
    assert lr.object == "list"
    assert lr.results[0]["id"] == "p1"
    assert lr.next_cursor == "cur"
    assert lr.has_more is True


def test_list_response_defaults():
    lr = ListResponse.model_validate({"object": "list", "results": []})
    assert lr.results == []
    assert lr.has_more is False
    assert lr.next_cursor is None


def test_page_model_partial_in_trash():
    page = Page.model_validate(
        {
            "object": "page",
            "id": "pg",
            "url": "https://notion.so/pg",
            "in_trash": False,
            "last_edited_time": "2026-06-01T00:00:00.000Z",
            "properties": {"제목": {"type": "title", "title": [{"plain_text": "T"}]}},
            "unexpected": "ignored",
        }
    )
    assert page.id == "pg"
    assert page.in_trash is False
    assert page_title(page.properties) == "T"


def test_page_requires_id():
    with pytest.raises(Exception):
        Page.model_validate({"object": "page"})


def test_database_model_data_sources():
    db = Database.model_validate(
        {
            "object": "database",
            "id": "db",
            "title": [{"plain_text": "My DB"}],
            "data_sources": [{"id": "ds1", "name": "Default"}],
            "in_trash": False,
        }
    )
    assert db.id == "db"
    assert rich_text_to_plain(db.title) == "My DB"
    assert db.data_sources[0]["id"] == "ds1"
    assert db.data_sources[0]["name"] == "Default"


def test_data_source_model_properties_schema():
    ds = DataSource.model_validate(
        {
            "object": "data_source",
            "id": "ds1",
            "title": [{"plain_text": "Tasks"}],
            "properties": {
                "Name": {"id": "title", "name": "Name", "type": "title"},
                "Status": {"id": "abc", "name": "Status", "type": "status"},
            },
        }
    )
    assert ds.id == "ds1"
    assert ds.properties["Status"]["type"] == "status"


def test_notion_error_model():
    e = NotionError.model_validate(
        {
            "object": "error",
            "status": 404,
            "code": "object_not_found",
            "message": "Could not find page with ID ...",
        }
    )
    assert e.status == 404
    assert e.code == "object_not_found"
    assert "Could not find" in e.message
