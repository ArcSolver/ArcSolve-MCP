"""Semantic Scholar 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·경로 빌더·limit/offset 검증(엔드포인트별 상한·relevance offset+limit<1000)·
build_params(fields·year·None 생략)·응답 모델 파싱(봉투/단건)·에러 모델. HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.services.semanticscholar.contract import (
    AUTHOR,
    AUTHOR_SEARCH,
    BASE_URL,
    DEFAULT_AUTHOR_FIELDS,
    DEFAULT_LIMIT,
    DEFAULT_PAPER_FIELDS,
    MAX_AUTHOR_LIMIT,
    MAX_PAPER_LIMIT,
    MAX_RELEVANCE_OFFSET_PLUS_LIMIT,
    MIN_LIMIT,
    PAPER,
    PAPER_SEARCH,
    Author,
    AuthorSearchResponse,
    ErrorResponse,
    Paper,
    PaperSearchResponse,
    author_path,
    build_params,
    paper_path,
    validate_limit,
    validate_relevance_window,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://api.semanticscholar.org/graph/v1"
    assert PAPER_SEARCH == "/paper/search"
    assert PAPER == "/paper"
    assert AUTHOR_SEARCH == "/author/search"
    assert AUTHOR == "/author"
    assert DEFAULT_LIMIT == 10
    assert MIN_LIMIT == 1
    assert MAX_PAPER_LIMIT == 100
    assert MAX_AUTHOR_LIMIT == 1000
    assert MAX_RELEVANCE_OFFSET_PLUS_LIMIT == 1000
    assert DEFAULT_PAPER_FIELDS == "paperId,title"
    assert DEFAULT_AUTHOR_FIELDS == "authorId,name"


# ─── 경로 빌더 ──────────────────────────────────────────────


def test_path_builders_keep_prefixed_ids_verbatim():
    # 접두 규칙은 S2가 그대로 받는다 — 정규화하지 않는다.
    assert paper_path("f3d594544126e202dbd81c186ca3ce448af5255c") == (
        "/paper/f3d594544126e202dbd81c186ca3ce448af5255c"
    )
    assert paper_path("DOI:10.22331/q-2018-08-06-79") == "/paper/DOI:10.22331/q-2018-08-06-79"
    assert paper_path("ARXIV:1801.00862") == "/paper/ARXIV:1801.00862"
    assert paper_path("CorpusId:44098998") == "/paper/CorpusId:44098998"
    assert author_path("7284134") == "/author/7284134"


def test_path_builders_strip_whitespace():
    assert paper_path("  DOI:10.1/x  ") == "/paper/DOI:10.1/x"
    assert author_path(" 7284134 ") == "/author/7284134"


# ─── limit 검증 ─────────────────────────────────────────────


def test_validate_limit_paper_bounds():
    assert validate_limit(MIN_LIMIT, maximum=MAX_PAPER_LIMIT) == 1
    assert validate_limit(MAX_PAPER_LIMIT, maximum=MAX_PAPER_LIMIT) == 100
    with pytest.raises(ValueError):
        validate_limit(0, maximum=MAX_PAPER_LIMIT)
    with pytest.raises(ValueError):
        validate_limit(MAX_PAPER_LIMIT + 1, maximum=MAX_PAPER_LIMIT)


def test_validate_limit_author_allows_up_to_1000():
    assert validate_limit(1000, maximum=MAX_AUTHOR_LIMIT) == 1000
    # 같은 1000이라도 paper 상한(100)에서는 거부된다.
    with pytest.raises(ValueError):
        validate_limit(1000, maximum=MAX_PAPER_LIMIT)


# ─── relevance offset+limit < 1000 ─────────────────────────


def test_validate_relevance_window_ok():
    validate_relevance_window(0, 10)  # 통과(예외 없음)
    validate_relevance_window(900, 99)  # 999 < 1000 통과


def test_validate_relevance_window_rejects_boundary_and_over():
    # 엄격히 < 1000: offset+limit == 1000도 거부된다(라이브: offset=999·limit=2 → 400).
    with pytest.raises(ValueError):
        validate_relevance_window(999, 1)  # = 1000
    with pytest.raises(ValueError):
        validate_relevance_window(999, 2)  # > 1000
    with pytest.raises(ValueError):
        validate_relevance_window(-1, 10)  # 음수 offset


# ─── build_params ──────────────────────────────────────────


def test_build_params_omits_none():
    assert build_params() == {}


def test_build_params_fields_and_year():
    params = build_params(query="dna", fields="title,year,authors.name", limit=5, offset=10, year="2015-2020")
    assert params["query"] == "dna"
    assert params["fields"] == "title,year,authors.name"
    assert params["limit"] == 5
    assert params["offset"] == 10
    assert params["year"] == "2015-2020"


def test_build_params_omits_empty_query_and_fields():
    params = build_params(query="", fields="", limit=3)
    assert "query" not in params
    assert "fields" not in params
    assert params == {"limit": 3}


def test_build_params_keeps_offset_zero():
    # offset=0은 유효값이므로 포함되어야 한다(None만 생략).
    params = build_params(offset=0)
    assert params["offset"] == 0


# ─── 응답 모델 ──────────────────────────────────────────────


def test_paper_model_partial_fields():
    p = Paper.model_validate(
        {
            "paperId": "f3d5",
            "title": "Quantum Computing in the NISQ era and beyond",
            "year": 2018,
            "venue": "Quantum",
            "citationCount": 9146,
            "externalIds": {"DOI": "10.22331/q-2018-08-06-79", "ArXiv": "1801.00862"},
            "authors": [{"authorId": "2313130", "name": "J. Preskill"}],
            "unexpected": "ignored",
        }
    )
    assert p.paperId == "f3d5"
    assert p.year == 2018
    assert p.citationCount == 9146
    assert p.externalIds["DOI"] == "10.22331/q-2018-08-06-79"
    assert p.authors[0]["name"] == "J. Preskill"


def test_paper_model_all_optional_when_fields_omitted():
    # fields 미요청이면 어떤 필드든 빠질 수 있다 — 빈 dict도 검증 통과.
    p = Paper.model_validate({})
    assert p.paperId is None
    assert p.title is None


def test_author_model_partial_fields():
    a = Author.model_validate(
        {
            "authorId": "7284134",
            "name": "D. Preskill",
            "paperCount": 4,
            "citationCount": 54,
            "hIndex": 2,
            "url": "https://www.semanticscholar.org/author/7284134",
            "x": "ign",
        }
    )
    assert a.authorId == "7284134"
    assert a.name == "D. Preskill"
    assert a.paperCount == 4
    assert a.hIndex == 2


def test_paper_search_response_envelope():
    body = {
        "total": 1440411,
        "offset": 0,
        "next": 1,
        "data": [{"paperId": "p1", "title": "T", "year": 2018}],
    }
    r = PaperSearchResponse.model_validate(body)
    assert r.total == 1440411
    assert r.offset == 0
    assert r.next == 1
    assert len(r.data) == 1
    assert r.data[0].paperId == "p1"


def test_paper_search_response_without_next():
    # next는 더 없으면 응답에서 생략된다 → None.
    r = PaperSearchResponse.model_validate({"total": 1, "offset": 0, "data": [{"paperId": "p1"}]})
    assert r.next is None
    assert r.total == 1


def test_author_search_response_envelope():
    body = {
        "total": 17,
        "offset": 0,
        "next": 1,
        "data": [{"authorId": "a1", "name": "X", "paperCount": 4}],
    }
    r = AuthorSearchResponse.model_validate(body)
    assert r.total == 17
    assert r.data[0].authorId == "a1"


def test_error_response_both_shapes():
    # 검증 실패/404: {"error":...}
    e1 = ErrorResponse.model_validate({"error": "Relevance search offset + limit must be < 1000."})
    assert "must be < 1000" in e1.error
    # 레이트리밋: {"message":..., "code":"429"}
    e2 = ErrorResponse.model_validate({"message": "Too Many Requests.", "code": "429"})
    assert e2.message == "Too Many Requests."
    assert e2.code == "429"
