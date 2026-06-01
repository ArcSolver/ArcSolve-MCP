"""Zotero 계약 검증 — 네트워크 없이 contract.py(+ tools._resolve/parse 로직)만 테스트.

검증 범위: 응답 모델·쿼리 제약·경로 빌더·백엔드 해석(_resolve)·페이지네이션 parse.
HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.http import parse_link_header
from arcsolve.services.zotero.contract import (
    API_KEY_HEADER,
    API_VERSION,
    API_VERSION_HEADER,
    DEFAULT_LIMIT,
    DEFAULT_LOCAL_BASE,
    LOCAL_USER_ID,
    MAX_BIB_ITEMS,
    MAX_ITEMKEYS,
    MAX_LIMIT,
    QMODES,
    WEB_BASE_URL,
    Collection,
    Fulltext,
    Tag,
    ZoteroItem,
    base_headers,
    build_search_params,
    collection_items_path,
    collections_path,
    group_prefix,
    item_children_path,
    item_fulltext_path,
    item_path,
    items_path,
    start_from_next_link,
    tags_path,
    user_prefix,
    validate_limit,
)
from arcsolve.services.zotero.tools import BackendError, ZoteroSettings, _resolve


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert WEB_BASE_URL == "https://api.zotero.org"
    assert DEFAULT_LOCAL_BASE == "http://localhost:23119/api"
    assert API_VERSION == "3"
    assert API_KEY_HEADER == "Zotero-API-Key"
    assert API_VERSION_HEADER == "Zotero-API-Version"
    assert DEFAULT_LIMIT == 25
    assert MAX_LIMIT == 100
    assert MAX_ITEMKEYS == 50
    assert MAX_BIB_ITEMS == 150
    assert LOCAL_USER_ID == "0"
    assert QMODES == ("titleCreatorYear", "everything")


def test_base_headers_with_and_without_key():
    assert base_headers(None) == {API_VERSION_HEADER: API_VERSION}
    h = base_headers("KEY123")
    assert h[API_VERSION_HEADER] == API_VERSION
    assert h[API_KEY_HEADER] == "KEY123"


# ─── prefix / 경로 빌더 ─────────────────────────────────────


def test_prefix_builders():
    assert user_prefix("12345") == "users/12345"
    assert group_prefix("987") == "groups/987"
    assert user_prefix(LOCAL_USER_ID) == "users/0"


def test_path_builders():
    p = "users/12345"
    assert items_path(p) == "users/12345/items"
    assert items_path(p, top=True) == "users/12345/items/top"
    assert item_path(p, "ABCD") == "users/12345/items/ABCD"
    assert item_children_path(p, "ABCD") == "users/12345/items/ABCD/children"
    assert item_fulltext_path(p, "ABCD") == "users/12345/items/ABCD/fulltext"
    assert collections_path(p) == "users/12345/collections"
    assert collections_path(p, top=True) == "users/12345/collections/top"
    assert collection_items_path(p, "COLL") == "users/12345/collections/COLL/items"
    assert tags_path(p) == "users/12345/tags"


# ─── 쿼리 제약 / 빌더 ───────────────────────────────────────


def test_validate_limit_bounds():
    assert validate_limit(1) == 1
    assert validate_limit(MAX_LIMIT) == MAX_LIMIT
    with pytest.raises(ValueError):
        validate_limit(0)
    with pytest.raises(ValueError):
        validate_limit(MAX_LIMIT + 1)


def test_build_search_params_omits_empty():
    params = build_search_params(limit=DEFAULT_LIMIT, start=0)
    assert params == {"limit": 25, "start": 0}  # q/qmode/itemType/tag/sort 모두 생략


def test_build_search_params_full():
    params = build_search_params(
        q="dna", item_type="book", tag="bio", qmode="everything", sort="dateModified",
        limit=50, start=25,
    )
    assert params["q"] == "dna"
    assert params["itemType"] == "book"  # 공식 카멜케이스 파라미터명
    assert params["tag"] == "bio"
    assert params["qmode"] == "everything"
    assert params["sort"] == "dateModified"
    assert params["limit"] == 50
    assert params["start"] == 25


def test_build_search_params_rejects_bad_limit():
    with pytest.raises(ValueError):
        build_search_params(limit=MAX_LIMIT + 1)


def test_build_search_params_rejects_bad_qmode():
    with pytest.raises(ValueError):
        build_search_params(qmode="nonsense")


# ─── 페이지네이션 parse ─────────────────────────────────────


def test_parse_link_header_extracts_rels():
    link = (
        '<https://api.zotero.org/users/1/items?start=25&limit=25>; rel="next", '
        '<https://api.zotero.org/users/1/items?start=200&limit=25>; rel="last"'
    )
    rels = parse_link_header(link)
    assert "start=25" in rels["next"]
    assert "start=200" in rels["last"]


def test_start_from_next_link():
    # Link URL의 쿼리에서 start를 뽑는다(콤마가 URL에 있어도 안전).
    assert start_from_next_link("https://api.zotero.org/users/1/items?start=50&limit=25") == 50
    assert start_from_next_link(None) is None
    assert start_from_next_link("https://api.zotero.org/users/1/items?limit=25") is None


# ─── 응답 모델 ──────────────────────────────────────────────


def test_zotero_item_loose_subobjects():
    # 최상위 key/version/library/links/meta/data — 서브키는 느슨히(UNVERIFIED).
    item = ZoteroItem.model_validate(
        {
            "key": "ABCD2345",
            "version": 1234,
            "library": {"type": "user", "id": 1, "whatever": "ok"},
            "links": {"self": {"href": "x"}, "unexpected": 1},
            "meta": {"creatorSummary": "Doe", "numChildren": 2},
            "data": {"itemType": "book", "title": "T", "extraField": "v"},
        }
    )
    assert item.key == "ABCD2345"
    assert item.version == 1234
    assert item.data["title"] == "T"
    assert item.library["type"] == "user"


def test_zotero_item_requires_key_and_version():
    with pytest.raises(Exception):
        ZoteroItem.model_validate({"version": 1})  # key 누락
    with pytest.raises(Exception):
        ZoteroItem.model_validate({"key": "X"})  # version 누락


def test_collection_model():
    c = Collection.model_validate(
        {"key": "COLL", "version": 5, "data": {"name": "My Coll", "parentCollection": False}}
    )
    assert c.key == "COLL"
    assert c.data["name"] == "My Coll"


def test_tag_model():
    t = Tag.model_validate({"tag": "biology", "meta": {"type": 0, "numItems": 3}})
    assert t.tag == "biology"
    assert t.meta["numItems"] == 3


def test_fulltext_text_document_fields():
    ft = Fulltext.model_validate({"content": "hello", "indexedChars": 5, "totalChars": 5})
    assert ft.content == "hello"
    assert ft.indexedChars == 5
    assert ft.totalChars == 5
    assert ft.indexedPages is None  # 텍스트 문서엔 pages 없음


def test_fulltext_pdf_fields():
    ft = Fulltext.model_validate({"content": "x", "indexedPages": 50, "totalPages": 50})
    assert ft.indexedPages == 50
    assert ft.totalPages == 50
    assert ft.indexedChars is None  # PDF엔 chars 없음


# ─── 백엔드 해석(_resolve) — 네트워크 없음 ──────────────────


def _settings(**kw) -> ZoteroSettings:
    # env 오염을 피하려고 model 인스턴스를 직접 만든다(_env_file 파싱 우회).
    return ZoteroSettings.model_construct(
        source=kw.get("source"),
        api_key=kw.get("api_key"),
        user_id=kw.get("user_id"),
        group_id=kw.get("group_id"),
        local_base=kw.get("local_base", DEFAULT_LOCAL_BASE),
    )


def test_resolve_auto_web_when_key_present():
    base, prefix, headers, source = _resolve(_settings(api_key="K", user_id="42"))
    assert source == "web"
    assert base == WEB_BASE_URL
    assert prefix == "users/42"
    assert headers[API_KEY_HEADER] == "K"
    assert headers[API_VERSION_HEADER] == "3"


def test_resolve_auto_local_when_no_key():
    base, prefix, headers, source = _resolve(_settings())
    assert source == "local"
    assert base == DEFAULT_LOCAL_BASE
    assert prefix == "users/0"
    assert API_KEY_HEADER not in headers  # 로컬은 무인증
    assert headers[API_VERSION_HEADER] == "3"


def test_resolve_group_takes_precedence():
    base, prefix, headers, source = _resolve(
        _settings(source="web", api_key="K", user_id="42", group_id="999")
    )
    assert source == "web"
    assert prefix == "groups/999"


def test_resolve_web_public_library_without_key():
    # 공개 라이브러리는 키 없이도 허용(헤더에서 키 생략).
    base, prefix, headers, source = _resolve(_settings(source="web", user_id="42"))
    assert source == "web"
    assert prefix == "users/42"
    assert API_KEY_HEADER not in headers


def test_resolve_web_without_user_or_group_errors():
    with pytest.raises(BackendError):
        _resolve(_settings(source="web", api_key="K"))


def test_resolve_local_custom_base_trailing_slash_stripped():
    base, prefix, headers, source = _resolve(
        _settings(source="local", local_base="http://127.0.0.1:23119/api/")
    )
    assert source == "local"
    assert base == "http://127.0.0.1:23119/api"  # 끝 슬래시 제거
    assert prefix == "users/0"


def test_resolve_bad_source_errors():
    with pytest.raises(BackendError):
        _resolve(_settings(source="cloud"))


def test_backend_error_is_value_error():
    # 도구가 ValueError 하나로 BackendError와 검증 오류를 함께 잡으므로 상속을 보장.
    assert issubclass(BackendError, ValueError)
