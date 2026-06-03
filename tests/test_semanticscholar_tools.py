"""Semantic Scholar 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·키 유무 확인.

get_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다.
키는 쿼리 파라미터가 아니라 `x-api-key` **헤더**로 들어가는지 확인한다(키 없으면 헤더 없음).
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.semanticscholar.tools import register

MOD = "arcsolve.services.semanticscholar.tools"


@pytest.fixture
def tools(monkeypatch, load_tools):
    """키 없는 기본 환경(공유 풀로 동작)."""
    monkeypatch.delenv("SEMANTICSCHOLAR_API_KEY", raising=False)
    return load_tools(register)


# ─── papers 검색 ────────────────────────────────────────────


async def test_search_papers_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "total": 1440411,
        "offset": 0,
        "next": 10,
        "data": [
            {
                "paperId": "f3d5",
                "title": "Quantum Computing in the NISQ era and beyond",
                "year": 2018,
                "authors": [
                    {"authorId": "1", "name": "J. Preskill"},
                    {"authorId": "2", "name": "A. Other"},
                ],
            }
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["s2_search_papers"](query="quantum", fields="title,year,authors.name")
    assert http.last["url"] == "https://api.semanticscholar.org/graph/v1/paper/search"
    # 키 없이도 동작 — x-api-key 헤더는 없어야 한다(None).
    assert http.last["headers"] is None
    assert http.last["params"]["query"] == "quantum"
    assert http.last["params"]["fields"] == "title,year,authors.name"
    assert http.last["params"]["limit"] == 10  # 기본
    assert http.last["params"]["offset"] == 0
    assert "총 1440411건" in out and "offset 0" in out and "다음 offset 10" in out
    assert "f3d5" in out and "Quantum Computing" in out and "2018" in out
    assert "J. Preskill 외 1명" in out


async def test_search_papers_no_network_when_limit_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_search_papers"](query="x", limit=101)  # paper 상한 100
    assert "limit" in out and "100" in out  # 계약 위반은 HTTP 전에 막힘
    assert not http.calls


async def test_search_papers_no_network_when_offset_plus_limit_too_big(
    tools, monkeypatch, recording_http
):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_search_papers"](query="x", offset=999, limit=2)  # = 1001
    assert "offset+limit" in out and "1000" in out
    assert not http.calls


async def test_search_papers_passes_year(tools, monkeypatch, recording_http):
    http = recording_http(ret={"total": 0, "offset": 0, "data": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_search_papers"](query="x", year="2010-2020")
    assert http.last["params"]["year"] == "2010-2020"
    assert "검색 결과 없음" in out


# ─── 키는 x-api-key 헤더(쿼리 파라미터 아님) ──────────────


async def test_api_key_goes_into_header_not_query(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("SEMANTICSCHOLAR_API_KEY", "SECRET")
    tools = load_tools(register)
    http = recording_http(ret={"total": 1, "offset": 0, "data": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)

    await tools["s2_search_papers"](query="x")
    # 헤더로 들어가야 한다(쿼리 파라미터 아님).
    assert http.last["headers"] == {"x-api-key": "SECRET"}
    assert "api_key" not in http.last["params"]
    assert "x-api-key" not in http.last["params"]


# ─── paper 단건 ────────────────────────────────────────────


async def test_get_paper_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "paperId": "f3d5",
        "title": "Quantum Computing in the NISQ era and beyond",
        "year": 2018,
        "venue": "Quantum",
        "citationCount": 9146,
        "externalIds": {"DOI": "10.22331/q-2018-08-06-79", "ArXiv": "1801.00862"},
        "authors": [{"authorId": "1", "name": "J. Preskill"}],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["s2_get_paper"](id="DOI:10.22331/q-2018-08-06-79", fields="title,citationCount")
    # 접두 ID는 그대로 경로에 들어간다(정규화 없음).
    assert http.last["url"] == (
        "https://api.semanticscholar.org/graph/v1/paper/DOI:10.22331/q-2018-08-06-79"
    )
    assert http.last["params"]["fields"] == "title,citationCount"
    assert "Quantum Computing" in out
    assert "2018" in out
    assert "9146" in out
    assert "J. Preskill" in out
    assert "Quantum" in out  # venue
    assert "10.22331/q-2018-08-06-79" in out  # DOI from externalIds


# ─── authors ────────────────────────────────────────────────


async def test_search_authors_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "total": 17,
        "offset": 0,
        "data": [
            {"authorId": "7284134", "name": "D. Preskill", "paperCount": 4, "citationCount": 54}
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["s2_search_authors"](query="preskill")
    assert http.last["url"] == "https://api.semanticscholar.org/graph/v1/author/search"
    assert http.last["params"]["query"] == "preskill"
    assert "총 17건" in out
    assert "D. Preskill" in out and "4편" in out and "54회" in out


async def test_search_authors_allows_limit_up_to_1000(tools, monkeypatch, recording_http):
    # author 상한은 1000 — paper(100)보다 크다.
    http = recording_http(ret={"total": 0, "offset": 0, "data": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_search_authors"](query="x", limit=1000)
    assert http.last["params"]["limit"] == 1000
    assert "검색 결과 없음" in out


async def test_search_authors_rejects_over_1000(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_search_authors"](query="x", limit=1001)
    assert "limit" in out and "1000" in out
    assert not http.calls


async def test_get_author_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "authorId": "7284134",
        "name": "D. Preskill",
        "paperCount": 4,
        "citationCount": 54,
        "hIndex": 2,
        "url": "https://www.semanticscholar.org/author/7284134",
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["s2_get_author"](id="7284134", fields="name,paperCount,hIndex,url")
    assert http.last["url"] == "https://api.semanticscholar.org/graph/v1/author/7284134"
    assert "D. Preskill" in out
    assert "4편" in out and "54회" in out
    assert "h-index: 2" in out
    assert "semanticscholar.org/author/7284134" in out


# ─── 에러 매핑 ──────────────────────────────────────────────


async def test_maps_400_with_error_message(tools, monkeypatch, recording_http):
    # 라이브: offset+limit 위반 → 400 {"error":"Relevance search offset + limit must be < 1000..."}.
    http = recording_http(
        exc=UpstreamError(
            400, {"error": "Relevance search offset + limit must be < 1000."}
        )
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_search_papers"](query="x")
    assert "400" in out
    assert "must be < 1000" in out  # error 텍스트 노출


async def test_maps_404_does_not_leak_non_dict_body(tools, monkeypatch, recording_http):
    # 비-dict(HTML 등) 404 본문이면 원문을 노출하지 않는다.
    http = recording_http(exc=UpstreamError(404, "<!doctype html><title>404</title>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_get_paper"](id="DOI:10.0000/nope")
    assert "404" in out and "접두" in out
    assert "doctype" not in out


async def test_maps_404_paper_json_error(tools, monkeypatch, recording_http):
    # 라이브: 없는 id → 404 {"error":"Paper with id ... not found"}.
    http = recording_http(exc=UpstreamError(404, {"error": "Paper with id DOI:x not found"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_get_paper"](id="DOI:x")
    assert "404" in out and "not found" in out


async def test_maps_429_rate_limit_message_and_code(tools, monkeypatch, recording_http):
    # 공유 풀 429: {"message":"Too Many Requests...","code":"429"}.
    http = recording_http(
        exc=UpstreamError(429, {"message": "Too Many Requests. Please wait...", "code": "429"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_search_papers"](query="x")
    assert "429" in out and "한도" in out
    assert "SEMANTICSCHOLAR_API_KEY" in out  # 키 권장 안내


async def test_maps_403_invalid_key(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, {"error": "forbidden"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["s2_get_author"](id="123")
    assert "403" in out and "API 키" in out
