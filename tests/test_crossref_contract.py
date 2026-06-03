"""Crossref 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·경로 빌더·build_params(rows/offset/order 검증·mailto 포함)·
응답 모델 파싱(봉투/단건/alias)·에러 모델. HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.services.crossref.contract import (
    BASE_URL,
    DEFAULT_ROWS,
    JOURNALS,
    MAX_OFFSET,
    MAX_ROWS,
    MIN_ROWS,
    WORKS,
    ErrorResponse,
    Journal,
    JournalResponse,
    JournalsResponse,
    ListMessage,
    Work,
    WorkResponse,
    WorksResponse,
    build_params,
    journal_path,
    validate_offset,
    validate_order,
    validate_rows,
    work_path,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://api.crossref.org"
    assert WORKS == "/works"
    assert JOURNALS == "/journals"
    assert DEFAULT_ROWS == 20
    assert MIN_ROWS == 0
    assert MAX_ROWS == 1000
    assert MAX_OFFSET == 10000


# ─── 경로 빌더 ──────────────────────────────────────────────


def test_path_builders():
    # DOI/ISSN은 그대로 경로에 넣는다(공백만 정리).
    assert work_path("10.5555/12345678") == "/works/10.5555/12345678"
    assert work_path("  10.1/x  ") == "/works/10.1/x"
    assert journal_path("2167-8359") == "/journals/2167-8359"


# ─── rows / offset / order 검증 ─────────────────────────────


def test_validate_rows_bounds():
    assert validate_rows(MIN_ROWS) == 0
    assert validate_rows(MAX_ROWS) == 1000
    with pytest.raises(ValueError):
        validate_rows(-1)
    with pytest.raises(ValueError):
        validate_rows(MAX_ROWS + 1)


def test_validate_offset_bounds():
    assert validate_offset(0) == 0
    assert validate_offset(MAX_OFFSET) == 10000
    with pytest.raises(ValueError):
        validate_offset(-1)
    with pytest.raises(ValueError):
        validate_offset(MAX_OFFSET + 1)


def test_validate_order():
    assert validate_order("asc") == "asc"
    assert validate_order("desc") == "desc"
    with pytest.raises(ValueError):
        validate_order("ascending")


# ─── build_params ──────────────────────────────────────────


def test_build_params_omits_none():
    assert build_params() == {}


def test_build_params_query_filter_sort_order():
    params = build_params(
        query="deep learning",
        filter="type:journal-article",
        sort="is-referenced-by-count",
        order="desc",
    )
    assert params["query"] == "deep learning"
    assert params["filter"] == "type:journal-article"
    assert params["sort"] == "is-referenced-by-count"
    assert params["order"] == "desc"


def test_build_params_rows_and_offset():
    params = build_params(rows=20, offset=40)
    assert params["rows"] == 20
    assert params["offset"] == 40


def test_build_params_includes_mailto_as_query():
    params = build_params(mailto="me@x.com")
    assert params["mailto"] == "me@x.com"  # 헤더가 아니라 쿼리 파라미터


def test_build_params_omits_empty_mailto():
    params = build_params(mailto=None, query="x")
    assert "mailto" not in params
    assert params == {"query": "x"}


def test_build_params_rejects_bad_rows():
    with pytest.raises(ValueError):
        build_params(rows=MAX_ROWS + 1)


def test_build_params_rejects_bad_offset():
    with pytest.raises(ValueError):
        build_params(offset=MAX_OFFSET + 1)


def test_build_params_rejects_bad_order():
    with pytest.raises(ValueError):
        build_params(order="up")


# ─── 응답 모델 (alias) ─────────────────────────────────────


def test_work_model_aliases_and_partial_fields():
    w = Work.model_validate(
        {
            "DOI": "10.1/x",
            "title": ["A Title"],
            "author": [{"given": "Jane", "family": "Doe", "sequence": "first"}],
            "type": "journal-article",
            "is-referenced-by-count": 42,
            "container-title": ["Journal of X"],
            "publisher": "ACME",
            "published": {"date-parts": [[2020, 5, 1]]},
            "unexpected": "ignored",
        }
    )
    assert w.doi == "10.1/x"  # DOI alias
    assert w.title == ["A Title"]
    assert w.author[0]["family"] == "Doe"
    assert w.is_referenced_by_count == 42  # 하이픈 alias
    assert w.container_title == ["Journal of X"]
    assert w.published["date-parts"][0][0] == 2020


def test_journal_model_aliases():
    j = Journal.model_validate(
        {
            "title": "PeerJ",
            "publisher": "PeerJ Inc.",
            "ISSN": ["2167-8359"],
            "issn-type": [{"type": "electronic", "value": "2167-8359"}],
            "counts": {"total-dois": 21163},
            "extra": "ign",
        }
    )
    assert j.title == "PeerJ"
    assert j.issn == ["2167-8359"]  # ISSN alias
    assert j.issn_type[0]["type"] == "electronic"  # issn-type alias
    assert j.counts["total-dois"] == 21163


def test_list_message_aliases():
    m = ListMessage.model_validate(
        {"total-results": 2998091, "items-per-page": 20, "items": [{"DOI": "10.1/x"}]}
    )
    assert m.total_results == 2998091  # total-results alias
    assert m.items_per_page == 20  # items-per-page alias
    assert m.items[0]["DOI"] == "10.1/x"


def test_works_response_envelope():
    body = {
        "status": "ok",
        "message-type": "work-list",
        "message": {
            "total-results": 5,
            "items-per-page": 20,
            "items": [{"DOI": "10.1/x", "title": ["T"]}],
        },
    }
    r = WorksResponse.model_validate(body)
    assert r.status == "ok"
    assert r.message.total_results == 5
    assert r.message.items[0]["DOI"] == "10.1/x"


def test_journals_response_envelope():
    body = {
        "status": "ok",
        "message": {"total-results": 3, "items": [{"title": "PeerJ"}]},
    }
    r = JournalsResponse.model_validate(body)
    assert r.message.total_results == 3
    assert r.message.items[0]["title"] == "PeerJ"


def test_work_response_single():
    # 단건은 message가 곧 Work 오브젝트.
    body = {
        "status": "ok",
        "message-type": "work",
        "message": {"DOI": "10.5555/12345678", "title": ["Single"], "type": "journal-article"},
    }
    r = WorkResponse.model_validate(body)
    assert r.message.doi == "10.5555/12345678"
    assert r.message.title == ["Single"]


def test_journal_response_single():
    body = {
        "status": "ok",
        "message-type": "journal",
        "message": {"title": "PeerJ", "publisher": "PeerJ Inc.", "ISSN": ["2167-8359"]},
    }
    r = JournalResponse.model_validate(body)
    assert r.message.title == "PeerJ"
    assert r.message.issn == ["2167-8359"]


def test_error_response_message_is_array():
    # 에러 봉투의 message는 array(성공 봉투의 object와 다름).
    e = ErrorResponse.model_validate(
        {
            "status": "failed",
            "message-type": "validation-failure",
            "message": [
                {
                    "type": "integer-not-valid",
                    "value": "1001",
                    "message": "Integer specified as 1001 but must be a positive integer "
                    "less than or equal to 1000. ",
                }
            ],
        }
    )
    assert e.status == "failed"
    assert "less than or equal to 1000" in e.message[0]["message"]
