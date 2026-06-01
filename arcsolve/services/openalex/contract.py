"""OpenAlex 학술 그래프 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 경로 빌더, 쿼리 제약/빌더, 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·JSON·읽기. 인증은 **선택**(키 없이도 동작). 키(`api_key`)와 polite-pool 이메일
(`mailto`)은 **쿼리 파라미터**다(헤더 아님). 페이지네이션/건수는 **응답 본문 meta**에 실리므로
코어 `get_json`만으로 충분하다(헤더 동사 불필요).

출처(공식 문서 — developers.openalex.org):
  - API 개요(base URL): https://developers.openalex.org/how-to-use-the-api/api-overview
  - 리스트/검색(search·filter·sort·per-page·page·cursor·meta 봉투):
    https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
  - Work 오브젝트(필드): https://developers.openalex.org/api-entities/works/work-object
  - Author 오브젝트(필드): https://developers.openalex.org/api-entities/authors/author-object
  - 인증/요금(api_key·mailto polite pool·레이트리밋): https://developers.openalex.org/guides/authentication
"""

from __future__ import annotations

import re

from pydantic import BaseModel

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base): https://developers.openalex.org/how-to-use-the-api/api-overview
#   ("https://api.openalex.org")
# 출처(엔드포인트 /works·/authors): get-lists-of-entities (entity 컬렉션 경로)
BASE_URL = "https://api.openalex.org"
WORKS = "/works"
AUTHORS = "/authors"


# bare DOI/ORCID는 OpenAlex가 거부(404)한다 — 네임스페이스 접두(doi:/orcid:)나 URL이라야 한다
# ("a bare identifier without any prefix or URL wrapper is not supported"). 자동 정규화한다.
# OpenAlex ID(W…/A…)·전체 URL·이미 접두가 붙은 값은 그대로 둔다.
_BARE_DOI = re.compile(r"^10\.\d{4,9}/.+$", re.IGNORECASE)
_BARE_ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", re.IGNORECASE)


def normalize_work_id(work_id: str) -> str:
    """bare DOI(`10.x/...`)면 `doi:` 접두를 붙인다(OpenAlex ID·URL·접두값은 그대로)."""
    wid = work_id.strip()
    return f"doi:{wid}" if _BARE_DOI.match(wid) else wid


def normalize_author_id(author_id: str) -> str:
    """bare ORCID(`0000-0000-0000-0000`)면 `orcid:` 접두를 붙인다(OpenAlex ID·URL은 그대로)."""
    aid = author_id.strip()
    return f"orcid:{aid}" if _BARE_ORCID.match(aid) else aid


def work_path(work_id: str) -> str:
    """단건 work 경로 /works/{id}. id = OpenAlex ID(`W…`)·DOI(bare/doi:/URL)·기타 접두.

    bare DOI는 `doi:`로 정규화한다(라이브 확인: bare DOI는 404, `doi:`는 200).
    출처: https://developers.openalex.org/api-entities/works/work-object
    """
    return f"{WORKS}/{normalize_work_id(work_id)}"


def author_path(author_id: str) -> str:
    """단건 author 경로 /authors/{id}. id = OpenAlex ID(`A…`)·ORCID(bare/orcid:/URL).

    bare ORCID는 `orcid:`로 정규화한다.
    출처: https://developers.openalex.org/api-entities/authors/author-object
    """
    return f"{AUTHORS}/{normalize_author_id(author_id)}"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 출처: https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
#   ("per-page" 1–200, page 기반 페이지네이션은 최대 10,000건까지 — 이후 cursor)
# 주의: **쿼리 파라미터명은 `per-page`(하이픈)**, 응답 본문 필드명은 `per_page`(언더스코어).
DEFAULT_PER_PAGE = 25
MIN_PER_PAGE = 1
MAX_PER_PAGE = 200
MAX_PAGE_RESULTS = 10000

# 공식 쿼리 파라미터명(정확한 철자 — 하이픈/언더스코어 혼동 방지).
# 출처: get-lists-of-entities(search·filter·sort·per-page·page) + authentication(api_key·mailto)
PARAM_SEARCH = "search"
PARAM_FILTER = "filter"
PARAM_SORT = "sort"
PARAM_PER_PAGE = "per-page"  # 하이픈!
PARAM_PAGE = "page"
PARAM_API_KEY = "api_key"
PARAM_MAILTO = "mailto"


def validate_per_page(per_page: int) -> int:
    """per-page를 1..200 범위로 검증한다(공식 제약).

    위반 시 ValueError(상류가 `{"error":...,"message":"...must be between 1 and 200"}`로
    400을 주기 전에 미리 막는다).
    출처: https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
    """
    if per_page < MIN_PER_PAGE or per_page > MAX_PER_PAGE:
        raise ValueError(
            f"per_page는 {MIN_PER_PAGE}..{MAX_PER_PAGE} 범위여야 합니다(현재 {per_page})."
        )
    return per_page


def build_params(
    *,
    query: str | None = None,
    filter: str | None = None,  # noqa: A002 (공식 파라미터명 "filter")
    sort: str | None = None,
    per_page: int | None = None,
    page: int | None = None,
    api_key: str | None = None,
    mailto: str | None = None,
) -> dict[str, str | int]:
    """리스트/검색 쿼리스트링을 만든다. None/빈값은 생략한다.

    - query → `search`(전문 검색)
    - filter → `filter`(attr:value, 콤마=AND / `|`=OR / `!`=NOT)
    - sort → `sort`
    - per_page → `per-page`(하이픈! 1..200 검증)
    - page → `page`
    - api_key → `api_key`(쿼리 파라미터, 선택)
    - mailto → `mailto`(polite pool, 선택)
    출처: https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
          + https://developers.openalex.org/guides/authentication
    """
    params: dict[str, str | int] = {}
    if query:
        params[PARAM_SEARCH] = query
    if filter:
        params[PARAM_FILTER] = filter
    if sort:
        params[PARAM_SORT] = sort
    if per_page is not None:
        params[PARAM_PER_PAGE] = validate_per_page(per_page)
    if page is not None:
        params[PARAM_PAGE] = page
    if api_key:
        params[PARAM_API_KEY] = api_key
    if mailto:
        params[PARAM_MAILTO] = mailto
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# 리스트 응답 봉투: {"meta":{...}, "results":[...], "group_by":[]}.
# 단건은 entity 오브젝트가 곧 최상위. extra="ignore"로 느슨히 받고(부분 모델),
# 확신하는 필드만 모델링한다.
# 출처(봉투/meta): https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities


class Meta(BaseModel):
    """리스트 응답의 meta 봉투.

    count(총 건수)·page·per_page(언더스코어!)·next_cursor(cursor 페이지네이션 시).
    cost_usd는 라이브 응답에서 관측됨 → float|None로 느슨히 둔다.
    출처: https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
    """

    model_config = {"extra": "ignore"}

    count: int
    page: int | None = None
    per_page: int | None = None  # 응답 본문 필드는 per_page(언더스코어)
    next_cursor: str | None = None
    cost_usd: float | None = None  # 라이브 관측 — 공식 산문에 표준화 명시는 약함


class Work(BaseModel):
    """단일 Work 오브젝트(부분).

    공식 필드: id · doi · display_name(+ title 별칭) · publication_year ·
    publication_date · type · cited_by_count · authorships(각 author.display_name/id) ·
    primary_location · open_access.
    출처: https://developers.openalex.org/api-entities/works/work-object
    """

    model_config = {"extra": "ignore"}

    id: str
    doi: str | None = None
    display_name: str | None = None
    title: str | None = None  # 공식상 display_name의 별칭
    publication_year: int | None = None
    publication_date: str | None = None
    type: str | None = None
    cited_by_count: int | None = None
    authorships: list[dict] | None = None  # 각 항목 author.display_name/author.id → dict로 느슨히
    primary_location: dict | None = None
    open_access: dict | None = None


class Author(BaseModel):
    """단일 Author 오브젝트(부분).

    공식 필드: id · display_name · orcid · works_count · cited_by_count.
    출처: https://developers.openalex.org/api-entities/authors/author-object
    """

    model_config = {"extra": "ignore"}

    id: str
    display_name: str | None = None
    orcid: str | None = None
    works_count: int | None = None
    cited_by_count: int | None = None


class WorksList(BaseModel):
    """`/works` 리스트 응답 봉투.

    출처: https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
    """

    model_config = {"extra": "ignore"}

    meta: Meta
    results: list[Work] = []


class AuthorsList(BaseModel):
    """`/authors` 리스트 응답 봉투.

    출처: https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
    """

    model_config = {"extra": "ignore"}

    meta: Meta
    results: list[Author] = []


class ErrorResponse(BaseModel):
    """OpenAlex 에러 봉투 `{error, message}`.

    예: per-page 범위 위반 시 message="...must be between 1 and 200".
    출처: https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
    """

    model_config = {"extra": "ignore"}

    error: str | None = None
    message: str | None = None
