"""OpenAlex 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·키 유무 확인.

get_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다.
키/mailto는 쿼리 파라미터로 들어가는지(헤더 아님) 확인한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.openalex.tools import register

MOD = "arcsolve.services.openalex.tools"


@pytest.fixture
def tools(monkeypatch, load_tools):
    """키/mailto 없는 기본 환경(키 없이도 동작)."""
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENALEX_MAILTO", raising=False)
    return load_tools(register)


# ─── works 검색 ─────────────────────────────────────────────


async def test_search_works_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "meta": {"count": 250, "page": 1, "per_page": 25},
        "results": [
            {
                "id": "W1",
                "display_name": "Deep Learning",
                "publication_year": 2015,
                "authorships": [
                    {"author": {"display_name": "Yann LeCun", "id": "A1"}},
                    {"author": {"display_name": "Yoshua Bengio", "id": "A2"}},
                ],
            }
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["openalex_search_works"](query="deep learning")
    assert http.last["url"] == "https://api.openalex.org/works"
    # 키 없이도 동작 — 키/mailto 파라미터는 없어야 한다.
    assert "api_key" not in http.last["params"]
    assert "mailto" not in http.last["params"]
    assert http.last["params"]["search"] == "deep learning"
    assert http.last["params"]["per-page"] == 25  # 하이픈!
    assert http.last["params"]["page"] == 1
    assert "총 250건" in out and "page 1" in out
    assert "W1" in out and "Deep Learning" in out
    assert "Yann LeCun 외 1명" in out


async def test_search_works_no_network_when_per_page_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_search_works"](per_page=201)
    assert "per_page" in out and "200" in out  # 계약 위반은 HTTP 전에 막힘
    assert not http.calls


async def test_search_works_filter_and_sort_params(tools, monkeypatch, recording_http):
    http = recording_http(ret={"meta": {"count": 0}, "results": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_search_works"](filter="is_oa:true", sort="cited_by_count:desc")
    assert http.last["params"]["filter"] == "is_oa:true"
    assert http.last["params"]["sort"] == "cited_by_count:desc"
    assert "검색 결과 없음" in out


# ─── 키/mailto는 쿼리 파라미터 ─────────────────────────────


async def test_credentials_go_into_query_params_not_headers(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("OPENALEX_API_KEY", "SECRET")
    monkeypatch.setenv("OPENALEX_MAILTO", "me@example.com")
    tools = load_tools(register)
    http = recording_http(ret={"meta": {"count": 1, "page": 1}, "results": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)

    await tools["openalex_search_works"](query="x")
    # 헤더가 아니라 쿼리 파라미터로 들어가야 한다.
    assert http.last["params"]["api_key"] == "SECRET"
    assert http.last["params"]["mailto"] == "me@example.com"
    assert http.last.get("headers") is None


# ─── work 단건 ─────────────────────────────────────────────


async def test_get_work_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "id": "https://openalex.org/W2741809807",
        "doi": "https://doi.org/10.7717/peerj.4375",
        "display_name": "The state of OA",
        "publication_year": 2018,
        "type": "article",
        "cited_by_count": 900,
        "authorships": [{"author": {"display_name": "Heather Piwowar", "id": "A1"}}],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["openalex_get_work"](work_id="W2741809807")
    assert http.last["url"] == "https://api.openalex.org/works/W2741809807"
    assert "The state of OA" in out
    assert "2018" in out
    assert "article" in out
    assert "900" in out
    assert "Heather Piwowar" in out


async def test_get_work_normalizes_bare_doi_in_path(tools, monkeypatch, recording_http):
    # bare DOI는 OpenAlex가 404 → doi: 네임스페이스로 정규화돼야 한다.
    http = recording_http(ret={"id": "W1", "display_name": "T"})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["openalex_get_work"](work_id="10.7717/peerj.4375")
    assert http.last["url"] == "https://api.openalex.org/works/doi:10.7717/peerj.4375"


# ─── authors ────────────────────────────────────────────────


async def test_search_authors_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "meta": {"count": 5, "page": 1},
        "results": [
            {"id": "A1", "display_name": "Jane Doe", "works_count": 99, "cited_by_count": 1234}
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["openalex_search_authors"](query="jane")
    assert http.last["url"] == "https://api.openalex.org/authors"
    assert http.last["params"]["search"] == "jane"
    assert "총 5건" in out
    assert "Jane Doe" in out and "99편" in out and "1234회" in out


async def test_get_author_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "id": "https://openalex.org/A5023888391",
        "display_name": "Heather Piwowar",
        "orcid": "https://orcid.org/0000-0003-1",
        "works_count": 100,
        "cited_by_count": 5000,
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["openalex_get_author"](author_id="A5023888391")
    assert http.last["url"] == "https://api.openalex.org/authors/A5023888391"
    assert "Heather Piwowar" in out
    assert "100편" in out and "5000회" in out
    assert "0000-0003-1" in out


# ─── 에러 매핑 ──────────────────────────────────────────────


async def test_maps_400_with_message(tools, monkeypatch, recording_http):
    http = recording_http(
        exc=UpstreamError(400, {"error": "Invalid query", "message": "per-page must be between 1 and 200"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_search_works"](query="x")
    assert "400" in out
    assert "between 1 and 200" in out  # 봉투 message 노출


async def test_maps_401_invalid_key(tools, monkeypatch, recording_http):
    # 라이브 확인: 무효/누락 키는 403이 아니라 401.
    http = recording_http(exc=UpstreamError(401, {"error": "Invalid or missing API key"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_search_works"](query="x")
    assert "401" in out and "API 키" in out


async def test_maps_403_credits(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, {"message": "credits exhausted"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_get_work"](work_id="W1")
    assert "403" in out and "크레딧" in out


async def test_404_does_not_leak_html_body(tools, monkeypatch, recording_http):
    # 404 본문이 HTML(비-dict)이면 원문을 노출하지 않는다.
    http = recording_http(exc=UpstreamError(404, "<!doctype html><title>404 Not Found</title>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_get_work"](work_id="Wbad")
    assert "404" in out
    assert "doctype" not in out and "<title>" not in out


async def test_maps_404(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(404, {"message": "not found"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_get_author"](author_id="Axxx")
    assert "404" in out


async def test_maps_429_rate_limit(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(429, {"message": "too many"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openalex_search_works"](query="x")
    assert "429" in out and "한도" in out
