"""Notion API 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 경로 빌더, 헤더/본문 빌더, 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델 + 순수 헬퍼).

전부 읽기. 인증은 **필수** Bearer 토큰(Internal Integration Token 또는 PAT) + 버전 헤더
`Notion-Version`. 페이지네이션은 list 응답 본문의 `next_cursor`/`has_more`(헤더 아님)이므로
코어 `get_json`/`post_json`만으로 충분하다(헤더 동사 불필요).

API 버전은 최신 **2026-03-11**로 고정한다. 이 버전부터 database는 **data source 컨테이너**이고
(`archived`는 `in_trash`로 대체됨), database 쿼리는 data source 쿼리로 옮겨졌다.

출처(공식 문서 — developers.notion.com):
  - API 레퍼런스 개요(base URL `https://api.notion.com/v1`): https://developers.notion.com/reference/intro
  - 버전 관리(Notion-Version, 최신 2026-03-11): https://developers.notion.com/reference/versioning
  - 2026-03-11 변경(archived→in_trash 등): https://developers.notion.com/changelog
  - 2025-09-03 업그레이드(data source 모델): https://developers.notion.com/docs/upgrade-guide-2025-09-03
  - Search: https://developers.notion.com/reference/post-search
  - Retrieve a page: https://developers.notion.com/reference/retrieve-a-page
  - Retrieve block children: https://developers.notion.com/reference/get-block-children
  - Retrieve a database: https://developers.notion.com/reference/retrieve-a-database
  - Retrieve a data source: https://developers.notion.com/reference/retrieve-a-data-source
  - Query a data source: https://developers.notion.com/reference/query-a-data-source
  - Rich text(모든 항목에 plain_text): https://developers.notion.com/reference/rich-text
  - 에러 봉투({object:"error",status,code,message}): https://developers.notion.com/reference/status-codes
"""

from __future__ import annotations

from pydantic import BaseModel

# ─── base URL / 버전 ────────────────────────────────────────
# 출처(base): https://developers.notion.com/reference/intro  ("https://api.notion.com/v1")
# 출처(버전): https://developers.notion.com/reference/versioning  (최신 2026-03-11)
BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"

# ─── 엔드포인트 상수 / 경로 빌더 ────────────────────────────
# 출처: 각 reference 페이지(post-search / retrieve-a-page / get-block-children /
#       retrieve-a-database / retrieve-a-data-source / query-a-data-source)
SEARCH = "/search"


def page_path(page_id: str) -> str:
    """단건 page 경로 GET /pages/{id}.

    출처: https://developers.notion.com/reference/retrieve-a-page
    """
    return f"/pages/{page_id}"


def blocks_children_path(block_id: str) -> str:
    """블록 자식 나열 경로 GET /blocks/{id}/children (page 본문 = page id를 block id로 사용).

    출처: https://developers.notion.com/reference/get-block-children
    """
    return f"/blocks/{block_id}/children"


def database_path(database_id: str) -> str:
    """단건 database 경로 GET /databases/{id} (→ data_sources 목록 반환).

    출처: https://developers.notion.com/reference/retrieve-a-database
    """
    return f"/databases/{database_id}"


def data_source_path(data_source_id: str) -> str:
    """단건 data source 경로 GET /data_sources/{id} (→ properties 스키마 반환).

    출처: https://developers.notion.com/reference/retrieve-a-data-source
    """
    return f"/data_sources/{data_source_id}"


def data_source_query_path(data_source_id: str) -> str:
    """data source 쿼리 경로 POST /data_sources/{id}/query (2025-09-03+; database 쿼리 대체).

    출처: https://developers.notion.com/reference/query-a-data-source
    """
    return f"/data_sources/{data_source_id}/query"


# ─── 헤더 ───────────────────────────────────────────────────
def headers(token: str) -> dict[str, str]:
    """공통 요청 헤더 — Bearer 인증 + 필수 버전 헤더.

    `Content-Type: application/json`은 본문 POST 시 httpx가 자동 설정한다.
    출처(인증/버전): https://developers.notion.com/reference/intro
                    + https://developers.notion.com/reference/versioning
    """
    return {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}


# ─── 페이지네이션 제약(공식) ────────────────────────────────
# 출처(page_size 최대 100, cursor 기반): https://developers.notion.com/reference/intro#pagination
# 응답 봉투에 `next_cursor`/`has_more`가 실린다(헤더 아님) → 코어 JSON 동사로 충분.
DEFAULT_PAGE_SIZE = 25
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100

# search filter는 `object`를 page/data_source로 한정한다.
# 출처: https://developers.notion.com/reference/post-search  (2025-09-03+: "database"→"data_source")
SEARCH_FILTER_VALUES = ("page", "data_source")


def validate_page_size(page_size: int) -> int:
    """page_size를 1..100 범위로 검증한다(공식 제약).

    위반 시 ValueError(상류가 validation_error 400을 주기 전에 미리 막는다).
    출처: https://developers.notion.com/reference/intro#pagination
    """
    if page_size < MIN_PAGE_SIZE or page_size > MAX_PAGE_SIZE:
        raise ValueError(
            f"page_size는 {MIN_PAGE_SIZE}..{MAX_PAGE_SIZE} 범위여야 합니다(현재 {page_size})."
        )
    return page_size


def validate_search_filter(filter_type: str) -> str:
    """search filter 값을 page|data_source로 검증한다.

    출처: https://developers.notion.com/reference/post-search
    """
    if filter_type not in SEARCH_FILTER_VALUES:
        raise ValueError(
            f"filter_type은 {' 또는 '.join(SEARCH_FILTER_VALUES)} 여야 합니다(현재 {filter_type!r})."
        )
    return filter_type


# ─── 본문 빌더 ──────────────────────────────────────────────
def build_search_body(
    *,
    query: str | None = None,
    filter_type: str | None = None,
    page_size: int | None = None,
    start_cursor: str | None = None,
) -> dict:
    """POST /search 본문을 만든다. None/빈값은 생략한다.

    - query → `query`(제목 전문 검색; 미지정 시 접근 가능한 전체를 나열)
    - filter_type → `filter` = {"value": page|data_source, "property": "object"}
    - page_size → `page_size`(1..100 검증)
    - start_cursor → `start_cursor`(다음 페이지)
    출처: https://developers.notion.com/reference/post-search
    """
    body: dict = {}
    if query:
        body["query"] = query
    if filter_type:
        body["filter"] = {"value": validate_search_filter(filter_type), "property": "object"}
    if page_size is not None:
        body["page_size"] = validate_page_size(page_size)
    if start_cursor:
        body["start_cursor"] = start_cursor
    return body


def build_query_body(
    *,
    filter: dict | None = None,  # noqa: A002 (공식 본문 키 "filter")
    sorts: list | None = None,
    page_size: int | None = None,
    start_cursor: str | None = None,
) -> dict:
    """POST /data_sources/{id}/query 본문을 만든다. None은 생략한다.

    `filter`/`sorts`는 Notion 필터/정렬 DSL을 **그대로 전달(pass-through)**한다 — 복합 DSL
    모델링은 MVP 스코프 밖(필요 시 호출자가 dict/list로 구성). page_size는 1..100 검증.
    출처: https://developers.notion.com/reference/query-a-data-source
    """
    body: dict = {}
    if filter:
        body["filter"] = filter
    if sorts:
        body["sorts"] = sorts
    if page_size is not None:
        body["page_size"] = validate_page_size(page_size)
    if start_cursor:
        body["start_cursor"] = start_cursor
    return body


def page_params(page_size: int | None = None, start_cursor: str | None = None) -> dict:
    """GET 페이지네이션 쿼리 파라미터(blocks children 등). None은 생략, page_size는 1..100 검증.

    출처: https://developers.notion.com/reference/get-block-children
          + https://developers.notion.com/reference/intro#pagination
    """
    params: dict[str, str | int] = {}
    if page_size is not None:
        params["page_size"] = validate_page_size(page_size)
    if start_cursor:
        params["start_cursor"] = start_cursor
    return params


# ─── 응답 모델 (전부 extra="ignore", 느슨한 부분 모델) ──────
# list 응답 봉투: {"object":"list","results":[...],"next_cursor":...,"has_more":...,"type":...}.
# 단건은 entity 오브젝트가 곧 최상위. 확신하는 필드만 모델링한다.


class ListResponse(BaseModel):
    """search / block children / data source query 공용 list 봉투.

    출처: https://developers.notion.com/reference/intro#pagination
    """

    model_config = {"extra": "ignore"}

    object: str | None = None
    results: list[dict] = []
    next_cursor: str | None = None
    has_more: bool = False
    type: str | None = None


class Page(BaseModel):
    """단일 Page 오브젝트(부분).

    공식 필드: object · id · url · in_trash(archived는 deprecated) · created_time ·
    last_edited_time · parent · properties(제목은 type=="title" 프로퍼티 안의 배열).
    출처: https://developers.notion.com/reference/page
    """

    model_config = {"extra": "ignore"}

    object: str | None = None
    id: str
    url: str | None = None
    in_trash: bool = False
    created_time: str | None = None
    last_edited_time: str | None = None
    parent: dict | None = None
    properties: dict = {}


class Database(BaseModel):
    """단일 Database 오브젝트(부분, 2026-03-11).

    공식 필드: object · id · title(rich_text 배열) · url · in_trash ·
    data_sources(자식 data source 목록 — 각 항목 id/name).
    출처: https://developers.notion.com/reference/retrieve-a-database
          + https://developers.notion.com/docs/upgrade-guide-2025-09-03
    """

    model_config = {"extra": "ignore"}

    object: str | None = None
    id: str
    title: list[dict] = []
    url: str | None = None
    in_trash: bool = False
    # TODO(provenance): data_sources[] 항목 스키마는 업그레이드 가이드 기준(id·name).
    # 레퍼런스 산문 명시가 약해 dict로 느슨히 받는다(필요한 id/name만 출력에서 사용).
    data_sources: list[dict] = []


class DataSource(BaseModel):
    """단일 Data Source 오브젝트(부분, 2025-09-03+).

    공식 필드: object · id · title(rich_text 배열) · properties(스키마맵: 각 값에 id/name/type) ·
    parent · in_trash.
    출처: https://developers.notion.com/reference/data-source
    """

    model_config = {"extra": "ignore"}

    object: str | None = None
    id: str
    title: list[dict] = []
    properties: dict = {}
    parent: dict | None = None
    in_trash: bool = False


class NotionError(BaseModel):
    """Notion 에러 봉투 `{object:"error", status, code, message}`.

    예: 400 {code:"validation_error"}, 404 {code:"object_not_found"}(통합 미공유가 흔함).
    출처: https://developers.notion.com/reference/status-codes
    """

    model_config = {"extra": "ignore"}

    object: str | None = None
    status: int | None = None
    code: str | None = None
    message: str | None = None


# ─── 순수 헬퍼(출력 가공용) ─────────────────────────────────
def rich_text_to_plain(items: list[dict] | None) -> str:
    """rich_text 배열을 평문으로 평탄화한다(각 항목의 `plain_text`를 이어붙임).

    모든 rich_text 항목은 `plain_text`를 가진다(text/mention/equation 공통).
    출처: https://developers.notion.com/reference/rich-text
    """
    if not items:
        return ""
    return "".join(it.get("plain_text") or "" for it in items)


def page_title(properties: dict | None) -> str:
    """page properties에서 제목을 추출한다.

    제목 프로퍼티의 **이름은 고정이 아니므로**(Title/Name/이름 등) `type=="title"`인 항목을
    스캔해 그 안의 `title` rich_text 배열을 평문화한다. 없으면 "(제목 없음)".
    출처: https://developers.notion.com/reference/page  (properties 안의 title 타입)
    """
    if properties:
        for prop in properties.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                text = rich_text_to_plain(prop.get("title"))
                if text:
                    return text
    return "(제목 없음)"


def block_plain_text(block: dict) -> str:
    """블록에서 본문 평문을 뽑는다.

    텍스트 블록(paragraph/heading_*/bulleted_list_item/numbered_list_item/to_do 등)은
    `block[block["type"]]["rich_text"]`에 본문이 있다. rich_text가 없는 블록(이미지/구분선 등)은 "".
    출처: https://developers.notion.com/reference/block
    """
    btype = block.get("type")
    if not btype:
        return ""
    payload = block.get(btype)
    if isinstance(payload, dict):
        return rich_text_to_plain(payload.get("rich_text"))
    return ""
