"""Wikipedia 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·UA/토큰 확인.

get_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다. User-Agent 헤더가 항상
실리는지(필수), Bearer는 WIKIPEDIA_API_TOKEN이 있을 때만 붙는지, lang/limit 검증이 HTTP 전에
막는지, Action API의 **HTTP 200 + error 봉투**와 403/404/429 매핑을 확인한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.wikipedia.tools import register

MOD = "arcsolve.services.wikipedia.tools"


@pytest.fixture
def tools(monkeypatch, load_tools):
    """기본 환경(무인증·기본 User-Agent·토큰 없음)."""
    monkeypatch.delenv("WIKIPEDIA_USER_AGENT", raising=False)
    monkeypatch.delenv("WIKIPEDIA_API_TOKEN", raising=False)
    return load_tools(register)


# ─── 검색 (per-wiki REST) ──────────────────────────────────


async def test_search_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "pages": [
            {
                "id": 25220,
                "key": "Quantum_computing",
                "title": "Quantum computing",
                "excerpt": '<span class="searchmatch">quantum</span> computing',
                "description": "Computer hardware technology",
            }
        ]
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikipedia_search"](query="quantum computing", limit=5)
    assert http.last["url"] == "https://en.wikipedia.org/w/rest.php/v1/search/page"
    assert http.last["params"]["q"] == "quantum computing"
    assert http.last["params"]["limit"] == 5
    # User-Agent는 항상 실린다(필수). 토큰 없으면 Bearer 없음.
    assert "User-Agent" in http.last["headers"]
    assert "Authorization" not in http.last["headers"]
    assert "Quantum_computing" in out and "Quantum computing" in out
    assert "Computer hardware technology" in out
    # excerpt는 HTML 태그가 제거된 평문으로.
    assert "<span" not in out and "searchmatch" not in out
    assert "quantum computing" in out


async def test_search_uses_lang_host(tools, monkeypatch, recording_http):
    http = recording_http(ret={"pages": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_search"](query="양자", lang="ko")
    assert http.last["url"] == "https://ko.wikipedia.org/w/rest.php/v1/search/page"
    assert "검색 결과 없음" in out


async def test_search_default_user_agent_present(tools, monkeypatch, recording_http):
    http = recording_http(ret={"pages": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikipedia_search"](query="x")
    assert "arcsolve" in http.last["headers"]["User-Agent"]


async def test_search_invalid_lang_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={"pages": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_search"](query="x", lang="en_US")
    assert "lang" in out
    assert not http.calls  # 형식 위반은 HTTP 전에 막힘


async def test_search_invalid_limit_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={"pages": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_search"](query="x", limit=101)  # 검색 상한 100
    assert "limit" in out and "100" in out
    assert not http.calls


# ─── User-Agent override / Bearer 토큰 ─────────────────────


async def test_user_agent_override_from_env(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("WIKIPEDIA_API_TOKEN", raising=False)
    monkeypatch.setenv("WIKIPEDIA_USER_AGENT", "(myapp.com, me@example.com)")
    tools = load_tools(register)
    http = recording_http(ret={"pages": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikipedia_search"](query="x")
    assert http.last["headers"]["User-Agent"] == "(myapp.com, me@example.com)"


async def test_api_token_adds_bearer_alongside_ua(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("WIKIPEDIA_USER_AGENT", raising=False)
    monkeypatch.setenv("WIKIPEDIA_API_TOKEN", "SECRET")
    tools = load_tools(register)
    http = recording_http(ret={"pages": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikipedia_search"](query="x")
    headers = http.last["headers"]
    assert "User-Agent" in headers  # UA는 항상
    assert headers["Authorization"] == "Bearer SECRET"  # 토큰 있을 때만 Bearer
    # 토큰은 헤더로만 — 쿼리 파라미터에 노출되지 않는다.
    assert "api_token" not in http.last["params"]


# ─── 요약 (rest_v1) ────────────────────────────────────────


async def test_summary_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "type": "standard",
        "title": "Paris",
        "description": "Capital of France",
        "extract": "Paris is the capital and largest city of France.",
        "lang": "en",
        "wikibase_item": "Q90",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Paris"}},
        "coordinates": {"lat": 48.8567, "lon": 2.3522},
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikipedia_summary"](title="Paris")
    # 제목은 path segment로 인코딩.
    assert http.last["url"] == "https://en.wikipedia.org/api/rest_v1/page/summary/Paris"
    assert "User-Agent" in http.last["headers"]
    assert "Paris" in out and "Capital of France" in out
    assert "Paris is the capital" in out
    assert "URL: https://en.wikipedia.org/wiki/Paris" in out
    assert "Wikidata: Q90" in out  # wikibase_item 노출
    assert "48.8567" in out and "2.3522" in out  # 좌표


async def test_summary_encodes_space_in_title(tools, monkeypatch, recording_http):
    http = recording_http(ret={"type": "standard", "title": "Quantum computing", "extract": "x"})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikipedia_summary"](title="Quantum computing")
    assert http.last["url"] == (
        "https://en.wikipedia.org/api/rest_v1/page/summary/Quantum%20computing"
    )


async def test_summary_disambiguation_note(tools, monkeypatch, recording_http):
    http = recording_http(
        ret={"type": "disambiguation", "title": "Mercury", "extract": "Mercury may refer to ..."}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_summary"](title="Mercury")
    assert "동음이의" in out


async def test_summary_404_not_found(tools, monkeypatch, recording_http):
    http = recording_http(
        exc=UpstreamError(404, {"type": "https://.../not_found", "title": "Not found."})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_summary"](title="ZZZNope")
    assert "404" in out and "문서를 찾을 수 없습니다" in out


# ─── 본문 (TextExtracts) ───────────────────────────────────


async def test_extract_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "batchcomplete": True,
        "query": {
            "pages": [
                {
                    "pageid": 23862,
                    "title": "Python (programming language)",
                    "extract": "Python is a language.",
                }
            ]
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikipedia_extract"](title="Python (programming language)", max_chars=200)
    assert http.last["url"] == "https://en.wikipedia.org/w/api.php"
    p = http.last["params"]
    assert p["action"] == "query" and p["prop"] == "extracts"
    assert p["explaintext"] == 1 and p["formatversion"] == 2 and p["redirects"] == 1
    assert p["exintro"] == 1  # intro_only 기본 True
    assert p["exchars"] == 200
    assert p["titles"] == "Python (programming language)"  # 쿼리 파라미터 — 별도 인코딩 안 함
    assert "Python is a language." in out


async def test_extract_full_text_omits_exintro(tools, monkeypatch, recording_http):
    http = recording_http(
        ret={"query": {"pages": [{"pageid": 1, "title": "X", "extract": "full"}]}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikipedia_extract"](title="X", intro_only=False)
    assert "exintro" not in http.last["params"]


async def test_extract_missing_page(tools, monkeypatch, recording_http):
    http = recording_http(
        ret={"query": {"pages": [{"ns": 0, "title": "ZZZNope", "missing": True}]}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_extract"](title="ZZZNope")
    assert "문서를 찾을 수 없습니다" in out


async def test_extract_invalid_max_chars_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_extract"](title="X", max_chars=2000)  # 상한 1200
    assert "max_chars" in out and "1200" in out
    assert not http.calls


async def test_extract_action_error_envelope_http_200(tools, monkeypatch, recording_http):
    # 라이브: 잘못된 파라미터 → HTTP 200 + {"error":{"code","info"}}.
    http = recording_http(
        ret={
            "error": {
                "code": "badinteger",
                "info": 'Invalid value "abc" for integer parameter "exchars".',
            }
        }
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_extract"](title="Paris")
    assert "Invalid value" in out  # error.info 노출
    assert "exchars" in out


# ─── 링크/분류 (Action API) ───────────────────────────────


async def test_links_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "query": {
            "pages": [
                {
                    "pageid": 23862,
                    "title": "Python (programming language)",
                    "links": [
                        {"ns": 0, "title": '"Hello, World!" program'},
                        {"ns": 0, "title": "ALGOL 68"},
                    ],
                    "categories": [{"ns": 14, "title": "Category:Programming languages"}],
                }
            ]
        }
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikipedia_links"](title="Python (programming language)", limit=3)
    assert http.last["url"] == "https://en.wikipedia.org/w/api.php"
    p = http.last["params"]
    assert p["prop"] == "links|categories"
    assert p["plnamespace"] == 0
    assert p["pllimit"] == 3 and p["cllimit"] == 3
    assert p["formatversion"] == 2 and p["redirects"] == 1
    assert "연결 문서" in out
    assert '"Hello, World!" program' in out and "ALGOL 68" in out
    assert "분류" in out and "Category:Programming languages" in out


async def test_links_missing_page(tools, monkeypatch, recording_http):
    http = recording_http(ret={"query": {"pages": [{"title": "ZZZNope", "missing": True}]}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_links"](title="ZZZNope")
    assert "문서를 찾을 수 없습니다" in out


async def test_links_no_links_or_categories(tools, monkeypatch, recording_http):
    http = recording_http(ret={"query": {"pages": [{"pageid": 1, "title": "Stub"}]}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_links"](title="Stub")
    assert "연결 문서: 없음" in out
    assert "분류: 없음" in out


async def test_links_invalid_limit_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_links"](title="X", limit=501)  # 링크 상한 500
    assert "limit" in out and "500" in out
    assert not http.calls


# ─── 에러 매핑 (전송 계층) ─────────────────────────────────


async def test_maps_403_user_agent(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "Forbidden"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_search"](query="x")
    assert "403" in out and "User-Agent" in out


async def test_maps_429_rate_limit(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(429, {"detail": "rate limited"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_search"](query="x")
    assert "429" in out and "한도" in out
    assert "WIKIPEDIA_API_TOKEN" in out  # 토큰 권장 안내


async def test_maps_404_extract(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(404, "not found"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikipedia_extract"](title="X")
    assert "404" in out and "문서를 찾을 수 없습니다" in out
