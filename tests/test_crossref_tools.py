"""Crossref 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·mailto 유무 확인.

get_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다.
mailto는 쿼리 파라미터로 들어가고(헤더 아님), User-Agent에도 명시되는지 확인한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.crossref.tools import register

MOD = "arcsolve.services.crossref.tools"


@pytest.fixture
def tools(monkeypatch, load_tools):
    """mailto 없는 기본 환경(무인증·public pool)."""
    monkeypatch.delenv("CROSSREF_MAILTO", raising=False)
    return load_tools(register)


# ─── works 검색 ─────────────────────────────────────────────


async def test_search_works_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "status": "ok",
        "message": {
            "total-results": 2998091,
            "items-per-page": 20,
            "items": [
                {
                    "DOI": "10.1/dl",
                    "title": ["Deep Learning"],
                    "published": {"date-parts": [[2015, 5, 1]]},
                    "author": [
                        {"given": "Yann", "family": "LeCun", "sequence": "first"},
                        {"given": "Yoshua", "family": "Bengio"},
                    ],
                }
            ],
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["crossref_search_works"](query="deep learning")
    assert http.last["url"] == "https://api.crossref.org/works"
    # mailto 없이도 동작 — mailto 파라미터는 없어야 한다.
    assert "mailto" not in http.last["params"]
    assert http.last["params"]["query"] == "deep learning"
    assert http.last["params"]["rows"] == 20
    assert http.last["params"]["offset"] == 0
    assert "총 2998091건" in out
    assert "10.1/dl" in out and "Deep Learning" in out and "2015" in out
    assert "Yann LeCun 외 1명" in out


async def test_search_works_no_network_when_rows_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_search_works"](rows=1001)
    assert "rows" in out and "1000" in out  # 계약 위반은 HTTP 전에 막힘
    assert not http.calls


async def test_search_works_no_network_when_offset_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_search_works"](offset=10001)
    assert "offset" in out and "10000" in out
    assert not http.calls


async def test_search_works_filter_sort_order_params(tools, monkeypatch, recording_http):
    http = recording_http(ret={"status": "ok", "message": {"total-results": 0, "items": []}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_search_works"](
        filter="type:journal-article", sort="is-referenced-by-count", order="desc"
    )
    assert http.last["params"]["filter"] == "type:journal-article"
    assert http.last["params"]["sort"] == "is-referenced-by-count"
    assert http.last["params"]["order"] == "desc"
    assert "검색 결과 없음" in out


async def test_search_works_bad_order_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_search_works"](order="up")
    assert "order" in out
    assert not http.calls


# ─── mailto는 쿼리 파라미터 + User-Agent ──────────────────


async def test_mailto_goes_into_query_params_and_user_agent(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("CROSSREF_MAILTO", "me@example.com")
    tools = load_tools(register)
    http = recording_http(ret={"status": "ok", "message": {"total-results": 1, "items": []}})
    monkeypatch.setattr(f"{MOD}.get_json", http)

    await tools["crossref_search_works"](query="x")
    # 쿼리 파라미터로 들어가야 한다.
    assert http.last["params"]["mailto"] == "me@example.com"
    # 공식 etiquette: User-Agent에도 mailto 명시.
    assert "mailto:me@example.com" in http.last["headers"]["User-Agent"]


async def test_user_agent_present_without_mailto(tools, monkeypatch, recording_http):
    http = recording_http(ret={"status": "ok", "message": {"total-results": 0, "items": []}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["crossref_search_works"](query="x")
    ua = http.last["headers"]["User-Agent"]
    assert "arcsolve" in ua
    assert "mailto:" not in ua  # mailto 없으면 붙이지 않는다


# ─── work 단건 ─────────────────────────────────────────────


async def test_get_work_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "status": "ok",
        "message-type": "work",
        "message": {
            "DOI": "10.5555/12345678",
            "title": ["The state of OA"],
            "published": {"date-parts": [[2018]]},
            "type": "journal-article",
            "is-referenced-by-count": 900,
            "container-title": ["PeerJ"],
            "publisher": "PeerJ Inc.",
            "author": [{"given": "Heather", "family": "Piwowar", "sequence": "first"}],
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["crossref_get_work"](doi="10.5555/12345678")
    assert http.last["url"] == "https://api.crossref.org/works/10.5555/12345678"
    assert "The state of OA" in out
    assert "2018" in out
    assert "journal-article" in out
    assert "900" in out
    assert "Heather Piwowar" in out
    assert "PeerJ" in out


# ─── journals ───────────────────────────────────────────────


async def test_search_journals_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "status": "ok",
        "message": {
            "total-results": 5,
            "items": [
                {"title": "PeerJ", "publisher": "PeerJ Inc.", "ISSN": ["2167-8359"]},
            ],
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["crossref_search_journals"](query="peerj")
    assert http.last["url"] == "https://api.crossref.org/journals"
    assert http.last["params"]["query"] == "peerj"
    assert "총 5건" in out
    assert "PeerJ" in out and "PeerJ Inc." in out and "2167-8359" in out


async def test_get_journal_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "status": "ok",
        "message-type": "journal",
        "message": {
            "title": "PeerJ",
            "publisher": "PeerJ Inc.",
            "ISSN": ["2167-8359"],
            "counts": {"total-dois": 21163},
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["crossref_get_journal"](issn="2167-8359")
    assert http.last["url"] == "https://api.crossref.org/journals/2167-8359"
    assert "PeerJ" in out
    assert "2167-8359" in out
    assert "21163" in out


# ─── 에러 매핑 ──────────────────────────────────────────────


async def test_maps_400_validation_failure_message_array(tools, monkeypatch, recording_http):
    # 라이브: rows 초과 → 400 {"message":[{"message":"...less than or equal to 1000"}]}.
    http = recording_http(
        exc=UpstreamError(
            400,
            {
                "status": "failed",
                "message-type": "validation-failure",
                "message": [
                    {"message": "Integer specified as 1001 but must be a positive integer "
                     "less than or equal to 1000. "}
                ],
            },
        )
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_search_works"](query="x")
    assert "400" in out
    assert "less than or equal to 1000" in out  # message 배열 첫 항목 노출


async def test_404_does_not_leak_plain_text_body(tools, monkeypatch, recording_http):
    # 404 본문은 text/plain `Resource not found.`(비-dict) → 원문을 노출하지 않는다.
    http = recording_http(exc=UpstreamError(404, "Resource not found."))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_get_work"](doi="10.0000/nope")
    assert "404" in out and "DOI" in out
    assert "Resource not found." not in out


async def test_maps_404_journal(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(404, "Resource not found."))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_get_journal"](issn="0000-0000")
    assert "404" in out


async def test_maps_429_rate_limit(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(429, "Too Many Requests"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_search_works"](query="x")
    assert "429" in out and "한도" in out


async def test_maps_504_gateway_timeout(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(504, "Gateway Timeout"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["crossref_search_works"](query="x")
    assert "504" in out
