"""Wikidata 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, id/타입/limit 검증, 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. **무인증**(키 없음)이나, Wikimedia는 **식별 가능한 `User-Agent`가 필수**다
(없으면 403/스로틀, 특히 WDQS가 엄격). 기본값을 `DEFAULT_USER_AGENT` 상수로 두고 env로 덮어쓴다.
(선택) `WIKIDATA_API_TOKEN`이 있으면 Bearer로 보내 레이트리밋을 완화한다 — 읽기는 토큰 없이도 동작.

세 종류의 상류를 함께 쓴다:
  - **Action API**(`/w/api.php`): `wbsearchentities` 엔티티 검색. ⚠️ 잘못된 파라미터에도 HTTP 200으로
    `{"error":{"code","info"}}` 봉투를 줄 수 있어 도구에서 본문의 `error`를 별도 확인한다.
  - **Wikibase REST API v1**(`/w/rest.php/wikibase/v1`): 엔티티 단건·statements 조회(2024-11 정식).
    레거시 `wbgetentities`보다 안정적이라 이쪽을 쓴다.
  - **WDQS**(`query.wikidata.org/sparql`): SPARQL 쿼리. 최대 60초 허용(코어 기본 10초로는 부족 →
    도구에서 timeout=60 전달). 구문 오류는 HTTP 400 + 텍스트/자바 예외 본문(원문 노출 금지).

출처(공식 문서):
  - Action API(wbsearchentities): https://www.mediawiki.org/wiki/Wikibase/API
  - Wikibase REST API: https://www.wikidata.org/wiki/Wikidata:REST_API
  - WDQS(SPARQL JSON·레이트리밋·60s 캡·UA 요구): https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(Action API base): https://www.mediawiki.org/wiki/Wikibase/API ("https://www.wikidata.org/w/api.php")
ACTION_API_URL = "https://www.wikidata.org/w/api.php"
# 출처(REST v1 base): https://www.wikidata.org/wiki/Wikidata:REST_API ("/w/rest.php/wikibase/v1")
REST_API_BASE = "https://www.wikidata.org/w/rest.php/wikibase/v1"
# 출처(WDQS): https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual
SPARQL_URL = "https://query.wikidata.org/sparql"

# ─── User-Agent (필수) ──────────────────────────────────────
# Wikimedia는 식별 가능한 User-Agent가 없으면 403/스로틀로 막는다(WDQS가 특히 엄격).
# 기본값을 상수로 두고 env(WIKIDATA_USER_AGENT)로 덮어쓴다(연락처 포함 권장).
# 출처: WDQS User Manual(User-Agent 정책) + Wikimedia User-Agent policy.
DEFAULT_USER_AGENT = "ArcSolve-MCP (github.com/ArcSolver/ArcSolve-MCP)"

# ─── 검색 limit / 타입 / id 패턴 제약(공식) ────────────────
# wbsearchentities: limit 1..50(기본 7). type ∈ {item, property, lexeme, form, sense}.
# 출처: https://www.mediawiki.org/wiki/Wikibase/API (api.php?action=help&modules=wbsearchentities)
DEFAULT_SEARCH_LIMIT = 7
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 50

VALID_SEARCH_TYPES = frozenset({"item", "property", "lexeme", "form", "sense"})

# 엔티티 id: item은 Q+숫자, property는 P+숫자(대문자). 출처: REST API / Wikibase 데이터 모델.
ITEM_ID_RE = re.compile(r"^Q\d+$")
PROPERTY_ID_RE = re.compile(r"^P\d+$")

# REST v1 엔티티 경로 세그먼트. 출처: https://www.wikidata.org/wiki/Wikidata:REST_API
ITEMS_PATH = "/entities/items"
PROPERTIES_PATH = "/entities/properties"


def item_path(qid: str) -> str:
    """REST v1 item 단건 경로 /entities/items/{Qid}.

    출처: Wikidata:REST_API (GET /entities/items/{item_id}).
    """
    return f"{ITEMS_PATH}/{qid}"


def property_path(pid: str) -> str:
    """REST v1 property 단건 경로 /entities/properties/{Pid}.

    출처: Wikidata:REST_API (GET /entities/properties/{property_id}).
    """
    return f"{PROPERTIES_PATH}/{pid}"


def item_statements_path(qid: str) -> str:
    """REST v1 item statements 경로 /entities/items/{Qid}/statements.

    출처: Wikidata:REST_API (GET /entities/items/{item_id}/statements).
    """
    return f"{ITEMS_PATH}/{qid}/statements"


# ─── 검증 (HTTP 전에 차단) ─────────────────────────────────


def validate_entity_id(entity_id: str) -> str:
    """엔티티 id를 Q\\d+(item) 또는 P\\d+(property)로 검증·정규화한다(공백 제거).

    둘 중 어느 형식도 아니면 ValueError(상류 호출 전에 막는다).
    출처: Wikibase 데이터 모델(item=Q+숫자, property=P+숫자).
    """
    eid = entity_id.strip()
    if ITEM_ID_RE.match(eid) or PROPERTY_ID_RE.match(eid):
        return eid
    raise ValueError(
        f"엔티티 id는 item(Q+숫자) 또는 property(P+숫자) 형식이어야 합니다(현재 {entity_id!r}). "
        "예: Q42, P31."
    )


def validate_item_id(entity_id: str) -> str:
    """item id를 Q\\d+로 검증·정규화한다(statements/엔티티 item 전용).

    출처: Wikibase 데이터 모델(item=Q+숫자).
    """
    eid = entity_id.strip()
    if ITEM_ID_RE.match(eid):
        return eid
    raise ValueError(f"item id는 Q+숫자 형식이어야 합니다(현재 {entity_id!r}). 예: Q42.")


def validate_property_id(property_id: str) -> str:
    """property id를 P\\d+로 검증·정규화한다.

    출처: Wikibase 데이터 모델(property=P+숫자).
    """
    pid = property_id.strip()
    if PROPERTY_ID_RE.match(pid):
        return pid
    raise ValueError(f"property id는 P+숫자 형식이어야 합니다(현재 {property_id!r}). 예: P31.")


def is_property_id(entity_id: str) -> bool:
    """entity_id가 property(P+숫자)면 True(REST 경로 분기용)."""
    return bool(PROPERTY_ID_RE.match(entity_id.strip()))


def validate_search_type(type_: str) -> str:
    """검색 type을 공식 enum {item, property, lexeme, form, sense}으로 검증한다.

    출처: https://www.mediawiki.org/wiki/Wikibase/API (wbsearchentities type 파라미터).
    """
    if type_ not in VALID_SEARCH_TYPES:
        raise ValueError(f"type은 {sorted(VALID_SEARCH_TYPES)} 중 하나여야 합니다(현재 {type_!r}).")
    return type_


def validate_search_limit(limit: int) -> int:
    """검색 limit을 1..50 범위로 검증한다(wbsearchentities).

    출처: https://www.mediawiki.org/wiki/Wikibase/API (wbsearchentities limit 1..50, 기본 7).
    """
    if limit < MIN_SEARCH_LIMIT or limit > MAX_SEARCH_LIMIT:
        raise ValueError(
            f"limit은 {MIN_SEARCH_LIMIT}..{MAX_SEARCH_LIMIT} 범위여야 합니다(현재 {limit})."
        )
    return limit


# ─── 응답 모델 (부분 모델 · extra="ignore") ────────────────
# 확신하는 필드만 모델링하고 나머지는 무시한다(느슨히 수신).


class SearchMatch(BaseModel):
    """`wbsearchentities` 결과 항목의 `match`(어디서 매치됐는지).

    출처: https://www.mediawiki.org/wiki/Wikibase/API (wbsearchentities 응답 search[].match).
    """

    model_config = {"extra": "ignore"}

    type: str | None = None
    language: str | None = None
    text: str | None = None


class SearchEntity(BaseModel):
    """`wbsearchentities` 응답 `search[]` 한 항목(부분).

    id·label·description·concepturi·url·aliases·match. label/description는 검색 language 기준.
    출처: https://www.mediawiki.org/wiki/Wikibase/API (wbsearchentities 응답 search[]).
    """

    model_config = {"extra": "ignore"}

    id: str | None = None
    label: str | None = None
    description: str | None = None
    concepturi: str | None = None
    url: str | None = None
    aliases: list[str] | None = None
    match: SearchMatch | None = None


class SearchResponse(BaseModel):
    """`wbsearchentities` 응답 봉투(부분).

    `search`(결과 배열) + `search-continue`(더 있으면 다음 offset). 잘못된 파라미터면 상류가
    HTTP 200으로 `error` 봉투를 줄 수 있어 그 키도 받는다(도구에서 우선 확인).
    출처: https://www.mediawiki.org/wiki/Wikibase/API (wbsearchentities) + Action API error 봉투.
    """

    model_config = {"extra": "ignore"}

    search: list[SearchEntity] = []
    search_continue: int | None = Field(default=None, alias="search-continue")
    error: dict | None = None  # Action API 200+error 봉투: {"code","info",...}


class Sitelink(BaseModel):
    """REST v1 엔티티 `sitelinks`의 한 항목(예: enwiki).

    출처: https://www.wikidata.org/wiki/Wikidata:REST_API (엔티티 sitelinks[wiki]: title·url).
    """

    model_config = {"extra": "ignore"}

    title: str | None = None
    url: str | None = None


class RestEntity(BaseModel):
    """Wikibase REST v1 엔티티 단건 응답(부분).

    id·labels(lang→값)·descriptions(lang→값)·aliases(lang→[값])·statements(Pxx→[...])·
    sitelinks(wiki→{title,url}). labels/descriptions는 다국어 dict라 출력에서 language 우선
    선택하고 en으로 폴백한다.
    출처: https://www.wikidata.org/wiki/Wikidata:REST_API (GET /entities/items|properties/{id}).
    """

    model_config = {"extra": "ignore"}

    id: str | None = None
    labels: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    statements: dict[str, list[Any]] = {}
    sitelinks: dict[str, Sitelink] = {}


class StatementValue(BaseModel):
    """REST v1 statement의 `value`(부분).

    type ∈ {"value","novalue","somevalue"}. `content`는 data_type별로 형태가 다르다:
      - string/url 등 → str
      - wikibase-item → "Qxx"(문자열 id)
      - time → {"time","precision","calendarmodel"}
      - quantity → {"amount","unit"}
      - monolingualtext → {"language","text"}
    형태가 가변이라 `content`는 Any로 받는다(novalue/somevalue면 content 없음).
    출처: https://www.wikidata.org/wiki/Wikidata:REST_API (statement value: type·content).
    """

    model_config = {"extra": "ignore"}

    type: str | None = None
    content: Any = None


class StatementProperty(BaseModel):
    """REST v1 statement의 `property`(id·data_type).

    출처: https://www.wikidata.org/wiki/Wikidata:REST_API (statement property: id·data_type).
    """

    model_config = {"extra": "ignore"}

    id: str | None = None
    data_type: str | None = None


class Statement(BaseModel):
    """REST v1 statement 한 항목(부분).

    id·rank·property({id,data_type})·value({type,content})·qualifiers. 출력에는 value만 쓴다.
    출처: https://www.wikidata.org/wiki/Wikidata:REST_API
        (GET /entities/items/{id}/statements 의 property→[statement]).
    """

    model_config = {"extra": "ignore"}

    id: str | None = None
    rank: str | None = None
    property: StatementProperty | None = None
    value: StatementValue | None = None
    qualifiers: list[Any] = []


# ─── REST 에러 봉투 ────────────────────────────────────────


class RestError(BaseModel):
    """Wikibase REST v1 에러 봉투(부분).

    `{"code": "...", "message": "..."}`. 404(엔티티 없음) 등에 온다.
    출처: https://www.wikidata.org/wiki/Wikidata:REST_API (error response: code·message).
    """

    model_config = {"extra": "ignore"}

    code: str | None = None
    message: str | None = None


# ─── SPARQL(WDQS) 결과 모델 ────────────────────────────────
# SPARQL 1.1 Query Results JSON Format: {"head":{"vars":[...]},"results":{"bindings":[{var:{...}}]}}.
# 각 binding 값: {"type":"uri"|"literal"|"bnode", "value": str, "datatype"?, "xml:lang"?}.
# 출처: https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual (SPARQL JSON 출력) +
#       https://www.w3.org/TR/sparql11-results-json/


class SparqlHead(BaseModel):
    """SPARQL JSON 결과의 `head`(투영 변수 목록).

    출처: https://www.w3.org/TR/sparql11-results-json/ (head.vars).
    """

    model_config = {"extra": "ignore"}

    vars: list[str] = []


class SparqlResults(BaseModel):
    """SPARQL JSON 결과의 `results.bindings`(행 배열, 각 행은 var→값 dict).

    값 dict는 형태가 가변(type·value·datatype·xml:lang)이라 dict로 느슨히 받는다.
    출처: https://www.w3.org/TR/sparql11-results-json/ (results.bindings[]).
    """

    model_config = {"extra": "ignore"}

    bindings: list[dict[str, dict]] = []


class SparqlResponse(BaseModel):
    """WDQS SPARQL JSON 응답 봉투.

    출처: https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual (SPARQL JSON 출력).
    """

    model_config = {"extra": "ignore"}

    head: SparqlHead = SparqlHead()
    results: SparqlResults = SparqlResults()
