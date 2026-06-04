"""Wikidata 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·인증 확인.

get_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다.
User-Agent는 항상 실리고(필수), Bearer는 WIKIDATA_API_TOKEN이 있을 때만 실린다.
SPARQL은 timeout=60을 넘기는지, 검증(잘못된 id/type/limit)이 HTTP 전에 막는지 확인한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.wikidata.tools import register

MOD = "arcsolve.services.wikidata.tools"


@pytest.fixture
def tools(monkeypatch, load_tools):
    """기본 환경(무인증·기본 User-Agent·토큰 없음)."""
    monkeypatch.delenv("WIKIDATA_USER_AGENT", raising=False)
    monkeypatch.delenv("WIKIDATA_API_TOKEN", raising=False)
    return load_tools(register)


# ─── 검색 (wbsearchentities) ───────────────────────────────


async def test_search_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "search": [
            {
                "id": "Q42",
                "label": "Douglas Adams",
                "description": "English science fiction writer and humorist",
            },
            {"id": "Q28846", "label": "Douglas Adams", "description": "British politician"},
        ],
        "success": 1,
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikidata_search"](query="douglas adams")
    assert http.last["url"] == "https://www.wikidata.org/w/api.php"
    p = http.last["params"]
    assert p["action"] == "wbsearchentities"
    assert p["search"] == "douglas adams"
    assert p["language"] == "en"
    assert p["type"] == "item"
    assert p["limit"] == 7  # 기본
    assert p["format"] == "json"
    # User-Agent는 항상 실린다(필수), Bearer는 없다(토큰 없음).
    assert "User-Agent" in http.last["headers"]
    assert "Authorization" not in http.last["headers"]
    assert "[Q42] Douglas Adams" in out
    assert "science fiction" in out


async def test_search_empty(tools, monkeypatch, recording_http):
    http = recording_http(ret={"search": [], "success": 1})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_search"](query="zzznotathing")
    assert "검색 결과 없음" in out


async def test_search_default_user_agent(tools, monkeypatch, recording_http):
    http = recording_http(ret={"search": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikidata_search"](query="x")
    assert "arcsolve" in http.last["headers"]["User-Agent"]


async def test_search_user_agent_override_from_env(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("WIKIDATA_USER_AGENT", "(myapp.com, me@example.com)")
    tools = load_tools(register)
    http = recording_http(ret={"search": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikidata_search"](query="x")
    assert http.last["headers"]["User-Agent"] == "(myapp.com, me@example.com)"


async def test_search_invalid_type_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_search"](query="x", type="entity")
    assert "type" in out
    assert not http.calls  # 잘못된 enum은 HTTP 전에 막힘


async def test_search_invalid_limit_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_search"](query="x", limit=51)
    assert "limit" in out and "50" in out
    assert not http.calls


async def test_search_action_api_200_error_envelope(tools, monkeypatch, recording_http):
    # Action API는 HTTP 200으로 error 봉투를 줄 수 있다 → 도구에서 본문 error 확인.
    http = recording_http(
        ret={"error": {"code": "param-missing", "info": "The required parameter ... missing."}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_search"](query="x")
    assert "검색 오류" in out and "missing" in out


# ─── 토큰(Bearer) ──────────────────────────────────────────


async def test_api_token_goes_into_bearer_header(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("WIKIDATA_API_TOKEN", "SECRET")
    tools = load_tools(register)
    http = recording_http(ret={"search": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikidata_search"](query="x")
    assert http.last["headers"]["Authorization"] == "Bearer SECRET"
    assert "User-Agent" in http.last["headers"]


# ─── 엔티티 단건 (REST v1) ─────────────────────────────────


async def test_entity_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "id": "Q42",
        "labels": {"en": "Douglas Adams", "ko": "더글러스 애덤스"},
        "descriptions": {"en": "English writer", "ko": "영국 작가"},
        "aliases": {"en": ["Douglas Noël Adams"]},
        "statements": {"P31": [{}], "P21": [{}], "P569": [{}]},
        "sitelinks": {
            "enwiki": {
                "title": "Douglas Adams",
                "url": "https://en.wikipedia.org/wiki/Douglas_Adams",
            }
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikidata_entity"](id="Q42")
    assert http.last["url"] == "https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q42"
    assert "User-Agent" in http.last["headers"]
    assert "Douglas Adams" in out
    assert "English writer" in out
    assert "Douglas Noël Adams" in out
    assert "statement 속성 수: 3" in out
    assert "en.wikipedia.org/wiki/Douglas_Adams" in out


async def test_entity_language_pick(tools, monkeypatch, recording_http):
    body = {
        "id": "Q42",
        "labels": {"en": "Douglas Adams", "ko": "더글러스 애덤스"},
        "descriptions": {"ko": "영국 작가"},
        "aliases": {},
        "statements": {},
        "sitelinks": {},
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_entity"](id="Q42", language="ko")
    assert "더글러스 애덤스" in out  # ko 우선
    assert "영국 작가" in out


async def test_entity_property_uses_properties_path(tools, monkeypatch, recording_http):
    body = {"id": "P31", "labels": {"en": "instance of"}, "statements": {}, "sitelinks": {}}
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["wikidata_entity"](id="P31")
    assert http.last["url"].endswith("/entities/properties/P31")


async def test_entity_invalid_id_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_entity"](id="notanid")
    assert "id" in out
    assert not http.calls  # 잘못된 형식은 HTTP 전에 막힘


async def test_entity_404_mapped(tools, monkeypatch, recording_http):
    http = recording_http(
        exc=UpstreamError(404, {"code": "item-not-found", "message": "Could not find ..."})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_entity"](id="Q999999999999")
    assert "404" in out and "찾을 수 없습니다" in out


# ─── statements (REST v1) ──────────────────────────────────


async def test_statements_request_and_output_varying_content(tools, monkeypatch, recording_http):
    # property id → [statement]. content가 data_type별로 다른 형태.
    body = {
        "P31": [
            {"id": "a", "value": {"type": "value", "content": "Q5"}},  # wikibase-item
        ],
        "P569": [
            {
                "id": "b",
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+1952-03-11T00:00:00Z",
                        "precision": 11,
                    },
                },
            }
        ],
        "P2048": [
            {
                "id": "c",
                "value": {
                    "type": "value",
                    "content": {"amount": "+1.83", "unit": "http://www.wikidata.org/entity/Q11573"},
                },
            }
        ],
        "P1477": [
            {"id": "d", "value": {"type": "value", "content": {"language": "en", "text": "Doug"}}}
        ],
        "P40": [
            {"id": "e", "value": {"type": "novalue"}},
            {"id": "f", "value": {"type": "somevalue"}},
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikidata_statements"](id="Q42")
    assert http.last["url"] == (
        "https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q42/statements"
    )
    assert http.last["params"] is None  # property 필터 없음
    assert "P31: Q5" in out
    assert "P569: +1952-03-11T00:00:00Z" in out  # time → content.time
    assert "P2048: +1.83 http://www.wikidata.org/entity/Q11573" in out  # quantity → amount unit
    assert "P1477: Doug" in out  # monolingualtext → text
    assert "(값 없음)" in out and "(미상)" in out  # novalue/somevalue


async def test_statements_property_filter(tools, monkeypatch, recording_http):
    body = {"P31": [{"id": "a", "value": {"type": "value", "content": "Q5"}}]}
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_statements"](id="Q42", property="P31")
    assert http.last["params"] == {"property": "P31"}
    assert "P31: Q5" in out


async def test_statements_empty(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_statements"](id="Q42")
    assert "statement가 없습니다" in out


async def test_statements_invalid_item_id_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_statements"](id="P31")  # property는 item 아님
    assert "item id" in out
    assert not http.calls


async def test_statements_invalid_property_filter_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_statements"](id="Q42", property="instance")
    assert "property id" in out
    assert not http.calls


# ─── SPARQL (WDQS) ─────────────────────────────────────────


async def test_sparql_request_passes_timeout_60(tools, monkeypatch, recording_http):
    body = {
        "head": {"vars": ["item", "itemLabel"]},
        "results": {
            "bindings": [
                {
                    "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q42"},
                    "itemLabel": {"type": "literal", "value": "Douglas Adams"},
                }
            ]
        },
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["wikidata_sparql"](query="SELECT ?item ?itemLabel WHERE {}")
    assert http.last["url"] == "https://query.wikidata.org/sparql"
    assert http.last["params"]["query"] == "SELECT ?item ?itemLabel WHERE {}"
    assert http.last["params"]["format"] == "json"
    assert http.last["timeout"] == 60.0  # WDQS는 최대 60초
    assert "User-Agent" in http.last["headers"]
    assert "item | itemLabel" in out  # 헤더 행
    assert "Q42" in out and "Douglas Adams" in out


async def test_sparql_limit_caps_displayed_rows(tools, monkeypatch, recording_http):
    bindings = [{"x": {"type": "literal", "value": str(i)}} for i in range(10)]
    body = {"head": {"vars": ["x"]}, "results": {"bindings": bindings}}
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_sparql"](query="SELECT ?x WHERE {}", limit=3)
    # 쿼리는 변형하지 않는다(표시만 제한).
    assert http.last["params"]["query"] == "SELECT ?x WHERE {}"
    assert "(10행 중 3행 표시)" in out
    # 표시된 값은 0,1,2 (3행)
    assert "\n0\n1\n2\n" in "\n" + out + "\n"


async def test_sparql_empty(tools, monkeypatch, recording_http):
    http = recording_http(ret={"head": {"vars": ["x"]}, "results": {"bindings": []}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_sparql"](query="SELECT ?x WHERE {}")
    assert "결과 행이 없습니다" in out


async def test_sparql_400_does_not_leak_raw_body(tools, monkeypatch, recording_http):
    # WDQS 400은 자바 예외/HTML 텍스트 본문 → 원문 노출 금지.
    raw = (
        "java.util.concurrent.ExecutionException: org.openrdf.query.MalformedQueryException: "
        'Encountered " <VAR1> "?bad "" at line 1 ... <html><body>stacktrace</body></html>'
    )
    http = recording_http(exc=UpstreamError(400, raw))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_sparql"](query="SELECT bad")
    assert "SPARQL 구문 오류(400)" in out
    assert "MalformedQuery" not in out  # 원문 노출 안 함
    assert "html" not in out
    assert "stacktrace" not in out


async def test_sparql_429_rate_limit(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(429, "Too Many Requests"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_sparql"](query="SELECT ?x WHERE {}")
    assert "429" in out and "한도" in out
    assert "5쿼리" in out or "60초" in out  # WDQS 캡 안내


async def test_sparql_500_server_error(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(503, "Service Unavailable"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_sparql"](query="SELECT ?x WHERE {}")
    assert "503" in out and "WDQS 서버 오류" in out


# ─── 403 (User-Agent) ──────────────────────────────────────


async def test_403_maps_to_user_agent_message(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "Forbidden"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["wikidata_entity"](id="Q42")
    assert "403" in out and "User-Agent" in out
