"""Wikidata 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수(Action API base·REST base·WDQS·기본 User-Agent)·경로 빌더(item/property/
statements)·검증(Q/P regex·type enum·limit 범위)·응답 모델 파싱(검색·REST 엔티티·statements의
가변 content(string/item/time/quantity/monolingualtext)·SPARQL head+bindings·에러 봉투).
HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.services.wikidata.contract import (
    ACTION_API_URL,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_USER_AGENT,
    MAX_SEARCH_LIMIT,
    REST_API_BASE,
    SPARQL_URL,
    VALID_SEARCH_TYPES,
    RestEntity,
    RestError,
    SearchResponse,
    SparqlResponse,
    Statement,
    StatementValue,
    is_property_id,
    item_path,
    item_statements_path,
    property_path,
    validate_entity_id,
    validate_item_id,
    validate_property_id,
    validate_search_limit,
    validate_search_type,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert ACTION_API_URL == "https://www.wikidata.org/w/api.php"
    assert REST_API_BASE == "https://www.wikidata.org/w/rest.php/wikibase/v1"
    assert SPARQL_URL == "https://query.wikidata.org/sparql"
    assert "ArcSolve-MCP" in DEFAULT_USER_AGENT
    assert "ArcSolver/ArcSolve-MCP" in DEFAULT_USER_AGENT


def test_search_limit_defaults():
    assert DEFAULT_SEARCH_LIMIT == 7
    assert MAX_SEARCH_LIMIT == 50


def test_valid_search_types():
    assert VALID_SEARCH_TYPES == {"item", "property", "lexeme", "form", "sense"}


# ─── 경로 빌더 ──────────────────────────────────────────────


def test_path_builders():
    assert item_path("Q42") == "/entities/items/Q42"
    assert property_path("P31") == "/entities/properties/P31"
    assert item_statements_path("Q42") == "/entities/items/Q42/statements"


# ─── id 검증 (Q/P regex) ───────────────────────────────────


def test_validate_entity_id_accepts_q_and_p():
    assert validate_entity_id("Q42") == "Q42"
    assert validate_entity_id("P31") == "P31"
    assert validate_entity_id("  Q5 ") == "Q5"  # 공백 정리


def test_validate_entity_id_rejects_bad():
    for bad in ("42", "q42", "Q", "QABC", "L123", "Q42x", ""):
        with pytest.raises(ValueError):
            validate_entity_id(bad)


def test_validate_item_id_only_q():
    assert validate_item_id("Q42") == "Q42"
    with pytest.raises(ValueError):
        validate_item_id("P31")  # property는 item 아님


def test_validate_property_id_only_p():
    assert validate_property_id("P31") == "P31"
    with pytest.raises(ValueError):
        validate_property_id("Q42")


def test_is_property_id():
    assert is_property_id("P31") is True
    assert is_property_id("Q42") is False


# ─── type / limit 검증 ─────────────────────────────────────


def test_validate_search_type():
    assert validate_search_type("item") == "item"
    assert validate_search_type("property") == "property"
    assert validate_search_type("lexeme") == "lexeme"
    with pytest.raises(ValueError):
        validate_search_type("entity")  # 잘못된 enum


def test_validate_search_limit_bounds():
    assert validate_search_limit(1) == 1
    assert validate_search_limit(50) == 50
    assert validate_search_limit(7) == 7
    with pytest.raises(ValueError):
        validate_search_limit(0)
    with pytest.raises(ValueError):
        validate_search_limit(51)


# ─── 검색 응답 모델 ────────────────────────────────────────


def test_search_response_parsing():
    body = {
        "searchinfo": {"search": "douglas adams"},
        "search": [
            {
                "id": "Q42",
                "title": "Q42",
                "label": "Douglas Adams",
                "description": "English science fiction writer and humorist",
                "concepturi": "http://www.wikidata.org/entity/Q42",
                "url": "//www.wikidata.org/wiki/Q42",
                "match": {"type": "label", "language": "en", "text": "Douglas Adams"},
                "aliases": ["Douglas Noël Adams"],
            }
        ],
        "search-continue": 7,
        "success": 1,
    }
    r = SearchResponse.model_validate(body)
    assert len(r.search) == 1
    ent = r.search[0]
    assert ent.id == "Q42"
    assert ent.label == "Douglas Adams"
    assert "science fiction" in ent.description
    assert ent.match.type == "label"
    assert ent.aliases == ["Douglas Noël Adams"]
    assert r.search_continue == 7  # search-continue alias
    assert r.error is None


def test_search_response_action_api_200_error_envelope():
    # Action API는 HTTP 200으로 error 봉투를 줄 수 있다.
    body = {
        "error": {
            "code": "unknown_type",
            "info": 'Unrecognized value for parameter "type": entity.',
        }
    }
    r = SearchResponse.model_validate(body)
    assert r.search == []
    assert r.error["code"] == "unknown_type"
    assert "Unrecognized" in r.error["info"]


# ─── REST 엔티티 모델 (labels/sitelinks) ───────────────────


def test_rest_entity_parsing_with_labels_and_sitelink():
    body = {
        "id": "Q42",
        "type": "item",
        "labels": {"en": "Douglas Adams", "ko": "더글러스 애덤스"},
        "descriptions": {"en": "English writer"},
        "aliases": {"en": ["Douglas Noël Adams", "Douglas Noel Adams"]},
        "statements": {
            "P31": [{"id": "x", "value": {"type": "value", "content": "Q5"}}],
            "P21": [{"id": "y", "value": {"type": "value", "content": "Q6581097"}}],
        },
        "sitelinks": {
            "enwiki": {
                "title": "Douglas Adams",
                "url": "https://en.wikipedia.org/wiki/Douglas_Adams",
            }
        },
    }
    ent = RestEntity.model_validate(body)
    assert ent.id == "Q42"
    assert ent.labels["en"] == "Douglas Adams"
    assert ent.labels["ko"] == "더글러스 애덤스"
    assert ent.descriptions["en"] == "English writer"
    assert ent.aliases["en"][0] == "Douglas Noël Adams"
    assert len(ent.statements) == 2  # P31, P21
    assert ent.sitelinks["enwiki"].title == "Douglas Adams"
    assert ent.sitelinks["enwiki"].url.endswith("/Douglas_Adams")


# ─── statements 모델 (가변 content) ────────────────────────


def test_statement_value_string_content():
    v = StatementValue.model_validate({"type": "value", "content": "some string"})
    assert v.type == "value"
    assert v.content == "some string"


def test_statement_value_wikibase_item_content():
    # wikibase-item은 content가 "Qxx" 문자열 id.
    v = StatementValue.model_validate({"type": "value", "content": "Q5"})
    assert v.content == "Q5"


def test_statement_value_time_content():
    # time은 content가 dict {time,precision,calendarmodel}.
    content = {
        "time": "+1952-03-11T00:00:00Z",
        "precision": 11,
        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
    }
    v = StatementValue.model_validate({"type": "value", "content": content})
    assert isinstance(v.content, dict)
    assert v.content["time"] == "+1952-03-11T00:00:00Z"
    assert v.content["precision"] == 11


def test_statement_value_quantity_content():
    # quantity는 content가 dict {amount,unit}.
    content = {"amount": "+1.83", "unit": "http://www.wikidata.org/entity/Q11573"}
    v = StatementValue.model_validate({"type": "value", "content": content})
    assert v.content["amount"] == "+1.83"
    assert "Q11573" in v.content["unit"]


def test_statement_value_monolingualtext_content():
    content = {"language": "en", "text": "hello"}
    v = StatementValue.model_validate({"type": "value", "content": content})
    assert v.content["text"] == "hello"


def test_statement_value_novalue_somevalue():
    nov = StatementValue.model_validate({"type": "novalue"})
    assert nov.type == "novalue"
    assert nov.content is None
    som = StatementValue.model_validate({"type": "somevalue"})
    assert som.type == "somevalue"


def test_statement_full_parsing():
    st = Statement.model_validate(
        {
            "id": "Q42$abc",
            "rank": "normal",
            "property": {"id": "P31", "data_type": "wikibase-item"},
            "value": {"type": "value", "content": "Q5"},
            "qualifiers": [],
        }
    )
    assert st.id == "Q42$abc"
    assert st.rank == "normal"
    assert st.property.id == "P31"
    assert st.property.data_type == "wikibase-item"
    assert st.value.content == "Q5"


# ─── REST 에러 봉투 ────────────────────────────────────────


def test_rest_error_parsing():
    err = RestError.model_validate(
        {"code": "item-not-found", "message": "Could not find an item with the ID Q999999999999"}
    )
    assert err.code == "item-not-found"
    assert "Q999999999999" in err.message


# ─── SPARQL 결과 모델 (head + bindings) ────────────────────


def test_sparql_response_head_and_bindings():
    body = {
        "head": {"vars": ["item", "itemLabel"]},
        "results": {
            "bindings": [
                {
                    "item": {
                        "type": "uri",
                        "value": "http://www.wikidata.org/entity/Q42",
                    },
                    "itemLabel": {
                        "type": "literal",
                        "xml:lang": "en",
                        "value": "Douglas Adams",
                    },
                },
                {
                    "item": {
                        "type": "uri",
                        "value": "http://www.wikidata.org/entity/Q5",
                    },
                    "itemLabel": {"type": "literal", "value": "human"},
                },
            ]
        },
    }
    r = SparqlResponse.model_validate(body)
    assert r.head.vars == ["item", "itemLabel"]
    assert len(r.results.bindings) == 2
    assert r.results.bindings[0]["item"]["value"].endswith("Q42")
    assert r.results.bindings[0]["itemLabel"]["value"] == "Douglas Adams"


def test_sparql_response_empty_bindings():
    body = {"head": {"vars": ["x"]}, "results": {"bindings": []}}
    r = SparqlResponse.model_validate(body)
    assert r.head.vars == ["x"]
    assert r.results.bindings == []
