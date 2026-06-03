"""Semantic Scholar Academic Graph API 학술 그래프 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 경로 빌더, 쿼리 제약/빌더, 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·JSON·읽기. 인증은 **선택**(키 없이 공유 풀로 동작). 키는 `x-api-key` **헤더**다
(OpenAlex의 쿼리 파라미터와 달리 헤더). 반환 필드는 **`fields` 파라미터**(콤마 구분)로 선택하고,
미지정 시 상류 기본 최소 필드(`paperId,title` / `authorId,name`)만 온다. 페이지네이션/건수는
**응답 본문**(`total`·`offset`·`next`)에 실리므로 코어 `get_json`만으로 충분하다(헤더 동사 불필요).

출처(공식 문서 — api.semanticscholar.org + 라이브):
  - OpenAPI(Swagger) 스펙(엔드포인트·쿼리 파라미터·limit/offset 제약·fields·응답 스키마):
    https://api.semanticscholar.org/api-docs/graph
    (원본 JSON: https://api.semanticscholar.org/graph/v1/swagger.json)
  - 공식 튜토리얼(base URL·fields·rate limit·x-api-key): https://www.semanticscholar.org/product/api/tutorial
  - 라이브 응답 확인: /paper/search · /paper/{id} · /author/search · /author/{id}
"""

from __future__ import annotations

from pydantic import BaseModel

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base): 튜토리얼 ("https://api.semanticscholar.org/graph/v1") + swagger basePath "/graph/v1"
# 출처(엔드포인트): swagger paths(/paper/search·/paper/{paper_id}·/author/search·/author/{author_id})
BASE_URL = "https://api.semanticscholar.org/graph/v1"
PAPER_SEARCH = "/paper/search"
PAPER = "/paper"
AUTHOR_SEARCH = "/author/search"
AUTHOR = "/author"


def paper_path(paper_id: str) -> str:
    """단건 paper 경로 /paper/{id}.

    id = S2 paperId(SHA 해시) 또는 외부 ID(접두 필수): `DOI:`·`ARXIV:`·`CorpusId:`·`MAG:`·
    `ACL:`·`PMID:`·`PMCID:`·`URL:`. 접두 없는 bare 값은 S2 paperId(해시)로 간주된다.
    값은 그대로 경로에 넣는다(정규화하지 않음 — S2가 접두 규칙을 그대로 받는다, 라이브 확인).
    없는 id는 404 + JSON `{"error":"Paper with id ... not found"}`.
    출처: swagger(/paper/{paper_id} path param 설명 — 허용 접두 목록) + 라이브(DOI: 200, bad 404)
    """
    return f"{PAPER}/{paper_id.strip()}"


def author_path(author_id: str) -> str:
    """단건 author 경로 /author/{id}. id = S2 authorId(숫자 문자열).

    출처: swagger(/author/{author_id} path param) + 라이브(/author/7284134 200)
    """
    return f"{AUTHOR}/{author_id.strip()}"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 출처: swagger
#   - /paper/search: limit 기본 100·최대 100, 추가로 relevance 검색은 offset+limit < 1000
#     (라이브: offset=999&limit=2 → 400 "Relevance search offset + limit must be < 1000").
#   - /author/search: limit 기본 100·최대 1000.
DEFAULT_LIMIT = 10  # 도구 기본값(검색 결과 과다 방지 — 상류 기본 100보다 보수적)
MIN_LIMIT = 1
MAX_PAPER_LIMIT = 100
MAX_AUTHOR_LIMIT = 1000
# relevance(검색) offset+limit 상한: 엄격히 < 1000 → 최대 999. 그 이상은 bulk/Datasets(범위 밖).
MAX_RELEVANCE_OFFSET_PLUS_LIMIT = 1000

# 공식 쿼리 파라미터명(정확한 철자). 출처: swagger(query·fields·limit·offset·year)
PARAM_QUERY = "query"
PARAM_FIELDS = "fields"
PARAM_LIMIT = "limit"
PARAM_OFFSET = "offset"
PARAM_YEAR = "year"

# 상류 기본 fields(미지정 시 반환되는 최소 필드). 출처: swagger(default "paperId,title"/"authorId,name")
DEFAULT_PAPER_FIELDS = "paperId,title"
DEFAULT_AUTHOR_FIELDS = "authorId,name"


def validate_limit(limit: int, *, maximum: int) -> int:
    """limit을 1..maximum 범위로 검증한다(엔드포인트별 maximum: paper=100·author=1000).

    위반 시 ValueError(상류 400 전에 미리 막는다).
    출처: swagger(/paper/search limit max 100, /author/search limit max 1000)
    """
    if limit < MIN_LIMIT or limit > maximum:
        raise ValueError(f"limit은 {MIN_LIMIT}..{maximum} 범위여야 합니다(현재 {limit}).")
    return limit


def validate_relevance_window(offset: int, limit: int) -> None:
    """relevance 검색의 offset+limit < 1000 제약을 검증한다(공식).

    위반 시 ValueError. 라이브: offset=999·limit=2 → 400
    `Relevance search offset + limit must be < 1000`. 그 이상은 bulk/Datasets API(범위 밖).
    출처: 라이브(/paper/search offset+limit 경계) + swagger(relevance 1000 cap)
    """
    if offset < 0:
        raise ValueError(f"offset은 0 이상이어야 합니다(현재 {offset}).")
    if offset + limit >= MAX_RELEVANCE_OFFSET_PLUS_LIMIT:
        raise ValueError(
            f"offset+limit은 {MAX_RELEVANCE_OFFSET_PLUS_LIMIT} 미만이어야 합니다"
            f"(현재 offset={offset}, limit={limit}). "
            "그 이상은 bulk 검색/Datasets API가 필요합니다(범위 밖)."
        )


def build_params(
    *,
    query: str | None = None,
    fields: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    year: str | None = None,
) -> dict[str, str | int]:
    """리스트/검색·단건 쿼리스트링을 만든다. None/빈값은 생략한다.

    - query → `query`(자유 전문 검색, 특수 구문 없음)
    - fields → `fields`(콤마 구분 필드 선택; 중첩은 `.`, 예: `authors.name`)
    - limit → `limit`(엔드포인트별 상한은 호출 측에서 validate_limit으로 검증)
    - offset → `offset`(0부터)
    - year → `year`(검색 전용 필터, 예: `2015`·`2010-2020`·`2015-`·`-2015`)
    출처: swagger(query·fields·limit·offset·year)
    """
    params: dict[str, str | int] = {}
    if query:
        params[PARAM_QUERY] = query
    if fields:
        params[PARAM_FIELDS] = fields
    if limit is not None:
        params[PARAM_LIMIT] = limit
    if offset is not None:
        params[PARAM_OFFSET] = offset
    if year:
        params[PARAM_YEAR] = year
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# 검색 응답 봉투: {"total", "offset", "next"(더 없으면 생략), "data":[...]}.
# 단건은 entity 오브젝트가 곧 최상위. extra="ignore"로 느슨히 받고(부분 모델),
# 확신하는 필드만 모델링한다. fields 파라미터로 어떤 필드든 빠질 수 있어 전부 Optional.
# 출처(봉투): swagger(paper/author search 응답 스키마) + 라이브(/paper/search·/author/search)


class Paper(BaseModel):
    """단일 Paper 오브젝트(부분).

    공식/라이브 필드: paperId(항상 반환) · title · year · venue · citationCount ·
    externalIds({DOI,ArXiv,CorpusId,MAG,...}) · authors(각 {authorId,name}).
    어느 필드든 `fields` 미요청 시 빠질 수 있어 paperId 외 전부 Optional.
    출처: swagger(Paper/FullPaper 스키마) + 라이브(/paper/{id}, /paper/search data[])
    """

    model_config = {"extra": "ignore"}

    paperId: str | None = None  # noqa: N815 (상류 필드명 camelCase 그대로)
    title: str | None = None
    year: int | None = None
    venue: str | None = None
    citationCount: int | None = None  # noqa: N815
    externalIds: dict | None = None  # noqa: N815 — {DOI,ArXiv,CorpusId,...} 중첩 → dict로 느슨히
    authors: list[dict] | None = None  # 각 항목 {authorId,name} → dict로 느슨히


class Author(BaseModel):
    """단일 Author 오브젝트(부분).

    공식/라이브 필드: authorId(항상 반환) · name · paperCount · citationCount · hIndex · url.
    출처: swagger(Author/AuthorWithPapers 스키마) + 라이브(/author/{id}, /author/search data[])
    """

    model_config = {"extra": "ignore"}

    authorId: str | None = None  # noqa: N815
    name: str | None = None
    paperCount: int | None = None  # noqa: N815
    citationCount: int | None = None  # noqa: N815
    hIndex: int | None = None  # noqa: N815
    url: str | None = None


class PaperSearchResponse(BaseModel):
    """`/paper/search` 리스트 응답 봉투.

    total(총 건수)·offset·next(더 있으면 다음 offset, 없으면 생략)·data.
    출처: swagger(paper search 응답) + 라이브(/paper/search)
    """

    model_config = {"extra": "ignore"}

    total: int | None = None
    offset: int | None = None
    next: int | None = None
    data: list[Paper] = []


class AuthorSearchResponse(BaseModel):
    """`/author/search` 리스트 응답 봉투.

    출처: swagger(author search 응답) + 라이브(/author/search)
    """

    model_config = {"extra": "ignore"}

    total: int | None = None
    offset: int | None = None
    next: int | None = None
    data: list[Author] = []


class ErrorResponse(BaseModel):
    """Semantic Scholar 에러 봉투.

    검증 실패/404는 `{"error": "..."}`(라이브: offset+limit 위반 400, 없는 id 404 모두 JSON).
    레이트리밋(공유 풀 429)은 `{"message": "...", "code": "429"}`(message+code 형태).
    둘 다 느슨히 받는다.
    출처: 라이브(/paper/search offset 위반 400, /paper/<bad> 404, 429 too-many-requests)
    """

    model_config = {"extra": "ignore"}

    error: str | None = None
    message: str | None = None
    code: str | None = None
