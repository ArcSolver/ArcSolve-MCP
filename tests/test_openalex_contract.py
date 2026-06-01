"""OpenAlex 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·경로 빌더·build_params(per-page 검증·키/mailto 포함·하이픈 파라미터명)·
응답 모델 파싱(봉투/단건)·에러 모델. HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.services.openalex.contract import (
    AUTHORS,
    BASE_URL,
    DEFAULT_PER_PAGE,
    MAX_PAGE_RESULTS,
    MAX_PER_PAGE,
    MIN_PER_PAGE,
    WORKS,
    Author,
    AuthorsList,
    ErrorResponse,
    Meta,
    Work,
    WorksList,
    author_path,
    build_params,
    validate_per_page,
    work_path,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://api.openalex.org"
    assert WORKS == "/works"
    assert AUTHORS == "/authors"
    assert DEFAULT_PER_PAGE == 25
    assert MIN_PER_PAGE == 1
    assert MAX_PER_PAGE == 200
    assert MAX_PAGE_RESULTS == 10000


# ─── 경로 빌더 ──────────────────────────────────────────────


def test_path_builders():
    # OpenAlex ID·전체 URL·이미 접두 붙은 값은 그대로 둔다.
    assert work_path("W2741809807") == "/works/W2741809807"
    assert work_path("doi:10.7717/peerj.4375") == "/works/doi:10.7717/peerj.4375"
    assert work_path("https://doi.org/10.7717/peerj.4375") == (
        "/works/https://doi.org/10.7717/peerj.4375"
    )
    assert author_path("A5023888391") == "/authors/A5023888391"
    assert author_path("https://orcid.org/0000-0002-1825-0097") == (
        "/authors/https://orcid.org/0000-0002-1825-0097"
    )


def test_path_builders_normalize_bare_doi_and_orcid():
    # bare DOI/ORCID는 OpenAlex가 404 → doi:/orcid: 네임스페이스로 정규화한다.
    assert work_path("10.7717/peerj.4375") == "/works/doi:10.7717/peerj.4375"
    assert author_path("0000-0002-1825-0097") == "/authors/orcid:0000-0002-1825-0097"


# ─── per-page 검증 ──────────────────────────────────────────


def test_validate_per_page_bounds():
    assert validate_per_page(MIN_PER_PAGE) == 1
    assert validate_per_page(MAX_PER_PAGE) == 200
    with pytest.raises(ValueError):
        validate_per_page(0)
    with pytest.raises(ValueError):
        validate_per_page(MAX_PER_PAGE + 1)


# ─── build_params ──────────────────────────────────────────


def test_build_params_omits_none():
    assert build_params() == {}


def test_build_params_uses_hyphen_per_page_name():
    params = build_params(per_page=25, page=2)
    assert "per-page" in params  # 하이픈! (응답 필드 per_page와 구분)
    assert "per_page" not in params
    assert params["per-page"] == 25
    assert params["page"] == 2


def test_build_params_search_filter_sort():
    params = build_params(query="dna", filter="is_oa:true", sort="cited_by_count:desc")
    assert params["search"] == "dna"
    assert params["filter"] == "is_oa:true"
    assert params["sort"] == "cited_by_count:desc"


def test_build_params_includes_key_and_mailto_as_query():
    params = build_params(api_key="K", mailto="me@x.com")
    assert params["api_key"] == "K"  # 헤더가 아니라 쿼리 파라미터
    assert params["mailto"] == "me@x.com"


def test_build_params_omits_empty_key_and_mailto():
    params = build_params(api_key=None, mailto=None, query="x")
    assert "api_key" not in params
    assert "mailto" not in params
    assert params == {"search": "x"}


def test_build_params_rejects_bad_per_page():
    with pytest.raises(ValueError):
        build_params(per_page=MAX_PER_PAGE + 1)


# ─── 응답 모델 ──────────────────────────────────────────────


def test_meta_model_per_page_underscore():
    # 응답 본문 필드는 per_page(언더스코어)·count·page·next_cursor·cost_usd.
    m = Meta.model_validate(
        {"count": 250, "page": 1, "per_page": 25, "next_cursor": None, "cost_usd": 0.0, "x": "ign"}
    )
    assert m.count == 250
    assert m.page == 1
    assert m.per_page == 25


def test_meta_requires_count():
    with pytest.raises(Exception):
        Meta.model_validate({"page": 1})


def test_work_model_partial_fields():
    w = Work.model_validate(
        {
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/10.1/x",
            "display_name": "A Title",
            "publication_year": 2020,
            "type": "article",
            "cited_by_count": 42,
            "authorships": [{"author": {"display_name": "Jane Doe", "id": "A1"}}],
            "open_access": {"is_oa": True},
            "unexpected": "ignored",
        }
    )
    assert w.id == "https://openalex.org/W123"
    assert w.display_name == "A Title"
    assert w.publication_year == 2020
    assert w.cited_by_count == 42
    assert w.authorships[0]["author"]["display_name"] == "Jane Doe"


def test_work_requires_id():
    with pytest.raises(Exception):
        Work.model_validate({"display_name": "no id"})


def test_author_model_partial_fields():
    a = Author.model_validate(
        {
            "id": "https://openalex.org/A123",
            "display_name": "Jane Doe",
            "orcid": "https://orcid.org/0000-0002-1",
            "works_count": 99,
            "cited_by_count": 1234,
            "extra": "ign",
        }
    )
    assert a.id == "https://openalex.org/A123"
    assert a.display_name == "Jane Doe"
    assert a.works_count == 99
    assert a.cited_by_count == 1234


def test_works_list_envelope():
    body = {
        "meta": {"count": 1, "page": 1, "per_page": 25},
        "results": [{"id": "W1", "display_name": "T", "publication_year": 2021}],
        "group_by": [],
    }
    wl = WorksList.model_validate(body)
    assert wl.meta.count == 1
    assert len(wl.results) == 1
    assert wl.results[0].id == "W1"


def test_authors_list_envelope():
    body = {
        "meta": {"count": 3, "page": 2},
        "results": [{"id": "A1", "display_name": "X"}],
    }
    al = AuthorsList.model_validate(body)
    assert al.meta.count == 3
    assert al.meta.page == 2
    assert al.results[0].id == "A1"


def test_error_response_model():
    e = ErrorResponse.model_validate(
        {"error": "Invalid query parameters", "message": "per-page param must be between 1 and 200"}
    )
    assert e.error == "Invalid query parameters"
    assert "between 1 and 200" in e.message
