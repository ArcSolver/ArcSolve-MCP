"""Crossref REST API 학술 메타데이터 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 경로 빌더, 쿼리 제약/빌더, 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·JSON·읽기. **무인증**(키 없음). polite pool은 `mailto` **쿼리 파라미터**로 명시한다
(env `CROSSREF_MAILTO`, 선택). 페이지네이션/건수는 **응답 본문 `message`**(`total-results`·
`items`·`items-per-page`)에 실리므로 코어 `get_json`만으로 충분하다(헤더 동사 불필요, OpenAlex와 동형).

출처(공식 문서 — CrossRef/rest-api-doc + api.crossref.org 라이브):
  - REST API README(엔드포인트·쿼리 파라미터·rows/offset 제약·sort/order·etiquette):
    https://github.com/CrossRef/rest-api-doc/blob/master/README.md
  - 응답 포맷(Work 오브젝트 필드): https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md
  - 공식 안내(retrieve metadata): https://www.crossref.org/documentation/retrieve-metadata/rest-api/
  - 라이브 응답 확인: https://api.crossref.org/works · /works/{doi} · /journals · /journals/{issn}
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base): README ("https://api.crossref.org/")
# 출처(엔드포인트 /works·/journals): README
#   ("/works/{doi}", "/journals", "/journals/{issn}")
BASE_URL = "https://api.crossref.org"
WORKS = "/works"
JOURNALS = "/journals"


def work_path(doi: str) -> str:
    """단건 work 경로 /works/{doi}.

    DOI는 그대로(bare `10.x/...` 또는 URL 래퍼) 경로에 넣는다. 라이브 확인: bare DOI 200.
    존재하지 않는 DOI는 404 + text/plain `Resource not found.`.
    출처: README ("/works/{doi} returns metadata for the specified Crossref DOI")
    """
    return f"{WORKS}/{doi.strip()}"


def journal_path(issn: str) -> str:
    """단건 journal 경로 /journals/{issn}.

    출처: README ("/journals/{issn} returns information about a journal with the given ISSN")
    """
    return f"{JOURNALS}/{issn.strip()}"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 출처: README
#   ("The maximum number rows you can ask for in one query is 1000")
#   ("Offsets for /works are limited to 10K") — deep paging은 cursor(범위 밖)
DEFAULT_ROWS = 20
MIN_ROWS = 0
MAX_ROWS = 1000
MAX_OFFSET = 10000

# 공식 쿼리 파라미터명(정확한 철자).
# 출처: README (query·query.bibliographic·filter·sort·order·rows·offset·select / mailto etiquette)
PARAM_QUERY = "query"
PARAM_FILTER = "filter"
PARAM_SORT = "sort"
PARAM_ORDER = "order"
PARAM_ROWS = "rows"
PARAM_OFFSET = "offset"
PARAM_SELECT = "select"
PARAM_MAILTO = "mailto"

# order는 asc/desc 둘 중 하나(공식). 출처: README ("asc or desc")
ORDER_ASC = "asc"
ORDER_DESC = "desc"
VALID_ORDERS = (ORDER_ASC, ORDER_DESC)


def validate_rows(rows: int) -> int:
    """rows를 0..1000 범위로 검증한다(공식 제약).

    위반 시 ValueError(상류가 400 validation-failure `Integer specified as N but must be a
    positive integer less than or equal to 1000`을 주기 전에 미리 막는다 — 라이브 확인).
    출처: README ("The maximum number rows you can ask for in one query is 1000")
    """
    if rows < MIN_ROWS or rows > MAX_ROWS:
        raise ValueError(f"rows는 {MIN_ROWS}..{MAX_ROWS} 범위여야 합니다(현재 {rows}).")
    return rows


def validate_offset(offset: int) -> int:
    """offset을 0..10000 범위로 검증한다(공식 deep-paging 한계).

    이 한계를 넘으려면 cursor 페이지네이션이 필요하나 MVP 범위 밖이다.
    출처: README ("Offsets for /works are limited to 10K")
    """
    if offset < 0 or offset > MAX_OFFSET:
        raise ValueError(
            f"offset은 0..{MAX_OFFSET} 범위여야 합니다(현재 {offset}). "
            "그 이상은 cursor 페이지네이션이 필요합니다(범위 밖)."
        )
    return offset


def validate_order(order: str) -> str:
    """order를 asc/desc로 검증한다(공식). 출처: README ("asc or desc")."""
    if order not in VALID_ORDERS:
        raise ValueError(f"order는 {VALID_ORDERS} 중 하나여야 합니다(현재 {order!r}).")
    return order


def build_params(
    *,
    query: str | None = None,
    filter: str | None = None,  # noqa: A002 (공식 파라미터명 "filter")
    sort: str | None = None,
    order: str | None = None,
    rows: int | None = None,
    offset: int | None = None,
    mailto: str | None = None,
) -> dict[str, str | int]:
    """리스트/검색 쿼리스트링을 만든다. None/빈값은 생략한다.

    - query → `query`(자유 전문 검색)
    - filter → `filter`(`name:value`, 콤마=AND. 예: `from-pub-date:2020-01-01,type:journal-article`)
    - sort → `sort`(예: `is-referenced-by-count`, `published`, `relevance`, `score`)
    - order → `order`(asc/desc 검증)
    - rows → `rows`(0..1000 검증)
    - offset → `offset`(0..10000 검증)
    - mailto → `mailto`(polite pool, 선택)
    출처: README (query·filter·sort·order·rows·offset·mailto)
    """
    params: dict[str, str | int] = {}
    if query:
        params[PARAM_QUERY] = query
    if filter:
        params[PARAM_FILTER] = filter
    if sort:
        params[PARAM_SORT] = sort
    if order is not None:
        params[PARAM_ORDER] = validate_order(order)
    if rows is not None:
        params[PARAM_ROWS] = validate_rows(rows)
    if offset is not None:
        params[PARAM_OFFSET] = validate_offset(offset)
    if mailto:
        params[PARAM_MAILTO] = mailto
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# 모든 응답 봉투: {"status","message-type","message-version","message":{...}}.
# 리스트면 message에 total-results·items-per-page·items·query, 단건이면 message가 곧 엔티티.
# extra="ignore"로 느슨히 받고(부분 모델), 확신하는 필드만 모델링한다.
# 출처(봉투): api_format.md + 라이브(/works·/journals)


class Work(BaseModel):
    """단일 Work 오브젝트(부분).

    공식 필드(api_format.md): DOI · title(Array of String) · author(Array of Contributor:
    given/family/ORCID/sequence) · type(String) · is-referenced-by-count(Number) ·
    container-title(Array of String) · publisher(String) · published(Partial Date:
    {date-parts:[[Y,M,D]]}) · URL · references-count.
    대문자/하이픈 필드명은 alias로 매핑한다(populate_by_name로 양쪽 다 허용).
    출처: https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    doi: str | None = Field(default=None, alias="DOI")
    title: list[str] | None = None
    author: list[dict] | None = None  # 각 항목 {given,family,ORCID,sequence} → dict로 느슨히
    type: str | None = None
    is_referenced_by_count: int | None = Field(default=None, alias="is-referenced-by-count")
    container_title: list[str] | None = Field(default=None, alias="container-title")
    publisher: str | None = None
    published: dict | None = None  # {date-parts:[[Y,M,D]]} (Partial Date)


class Journal(BaseModel):
    """단일 Journal 오브젝트(부분).

    공식/라이브 필드: title(String) · publisher(String) · ISSN(Array of String) ·
    issn-type(Array of {type,value}) · subjects(Array) · counts({total-dois,...}).
    출처: 라이브 /journals · /journals/{issn} (message-type "journal")
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    title: str | None = None
    publisher: str | None = None
    issn: list[str] | None = Field(default=None, alias="ISSN")
    issn_type: list[dict] | None = Field(default=None, alias="issn-type")
    subjects: list[dict] | None = None
    counts: dict | None = None


class ListMessage(BaseModel):
    """리스트 응답의 `message` 봉투(items 포함).

    total-results(총 건수)·items-per-page·items. query({start-index,search-terms})는 무시.
    출처: api_format.md + 라이브 (/works·/journals 리스트)
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    total_results: int | None = Field(default=None, alias="total-results")
    items_per_page: int | None = Field(default=None, alias="items-per-page")
    items: list[dict] = []


class WorksResponse(BaseModel):
    """`/works` 리스트 응답 봉투 전체.

    {status, message-type, message-version, message:{total-results, items:[...]}}.
    출처: 라이브 /works (message-type "work-list")
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    status: str | None = None
    message: ListMessage


class JournalsResponse(BaseModel):
    """`/journals` 리스트 응답 봉투 전체.

    출처: 라이브 /journals (message-type "journal-list")
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    status: str | None = None
    message: ListMessage


class WorkResponse(BaseModel):
    """`/works/{doi}` 단건 응답 봉투 — message가 곧 Work.

    출처: 라이브 /works/{doi} (message-type "work")
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    status: str | None = None
    message: Work


class JournalResponse(BaseModel):
    """`/journals/{issn}` 단건 응답 봉투 — message가 곧 Journal.

    출처: 라이브 /journals/{issn} (message-type "journal")
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    status: str | None = None
    message: Journal


class ErrorResponse(BaseModel):
    """Crossref validation-failure 에러 봉투(JSON일 때).

    라이브 확인: rows 범위 위반 → 400 `{"status":"failed",
    "message-type":"validation-failure","message":[{"type","value","message"}]}`.
    주의: 성공 봉투의 message는 **object**지만 에러 봉투의 message는 **array**다(서로 다른 스키마).
    404(없는 DOI)는 본문이 text/plain `Resource not found.`라 이 모델로 파싱되지 않는다.
    출처: 라이브 (/works?rows=1001)
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    status: str | None = None
    message: list[dict] | None = None
