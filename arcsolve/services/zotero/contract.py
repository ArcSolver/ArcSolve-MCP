"""Zotero 라이브러리 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 경로 빌더, 쿼리 제약, 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

**한 서비스 = 두 백엔드(web / local).** 로컬 데스크톱 API는 Web API v3를 미러하므로
경로·쿼리·응답 모델이 거의 동일하다 — 차이는 base URL + 인증뿐. 따라서 이 계약은
양쪽에서 그대로 쓰이고, 백엔드 분기는 tools.py의 ZoteroSettings._resolve()가 담당한다.

출처(공식 문서/공식 레포 소스):
  - Web API v3 basics(엔드포인트/쿼리/페이지네이션/백오프/제약):
    https://www.zotero.org/support/dev/web_api/v3/basics
  - 아이템 타입·필드: https://www.zotero.org/support/dev/web_api/v3/types_and_fields
  - 전문(Full-Text) 콘텐츠 포맷:
    https://www.zotero.org/support/dev/web_api/v3/fulltext_content
  - 로컬 API 1차 출처(공식 레포 소스 주석 — 전용 산문 문서 없음):
    https://github.com/zotero/zotero/blob/main/chrome/content/zotero/xpcom/server/server_localAPI.js
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# ─── base URL / 버전 / 인증 헤더 ─────────────────────────────
# web base + 로컬 기본 base. 로컬은 server_localAPI.js가 `localhost:23119` 에 `/api` prefix로
# Web API v3 미러를 서빙한다. 공통으로 `Zotero-API-Version: 3` 을 보낸다.
# 출처(web): https://www.zotero.org/support/dev/web_api/v3/basics ("https://api.zotero.org")
# 출처(local): server_localAPI.js — "localhost:23119 by default", `const LOCAL_API_VERSION = 3;`
WEB_BASE_URL = "https://api.zotero.org"
DEFAULT_LOCAL_BASE = "http://localhost:23119/api"
API_VERSION = "3"

# 인증 헤더 이름. web은 Zotero-API-Key(공개 라이브러리면 생략 가능). local은 무인증.
# 출처: https://www.zotero.org/support/dev/web_api/v3/basics ("Zotero-API-Key" 헤더)
API_KEY_HEADER = "Zotero-API-Key"
API_VERSION_HEADER = "Zotero-API-Version"


def base_headers(api_key: str | None = None) -> dict[str, str]:
    """공통 요청 헤더. api_key가 있으면 Zotero-API-Key를 더한다(공개/local은 생략).

    출처: https://www.zotero.org/support/dev/web_api/v3/basics
    """
    headers = {API_VERSION_HEADER: API_VERSION}
    if api_key:
        headers[API_KEY_HEADER] = api_key
    return headers


# ─── 라이브러리 prefix 빌더 ─────────────────────────────────
# web: users/<userID> 또는 groups/<groupID>. local: 로그인 사용자 데이터는 항상 users/0.
# 출처(web prefix): https://www.zotero.org/support/dev/web_api/v3/basics
#   ("/users/<userID>" / "/groups/<groupID>" = "<userOrGroupPrefix>")
# 출처(local users/0): server_localAPI.js — "Only data for the logged-in user is available
#   locally -- use userID 0"
LOCAL_USER_ID = "0"


def user_prefix(user_id: str) -> str:
    """users/<userID> 형태의 라이브러리 prefix."""
    return f"users/{user_id}"


def group_prefix(group_id: str) -> str:
    """groups/<groupID> 형태의 라이브러리 prefix."""
    return f"groups/{group_id}"


# ─── 엔드포인트 경로 빌더(prefix 상대) ──────────────────────
# 모든 경로는 <base>/<prefix>/... 로 조합된다. prefix는 위 빌더가 만든다.
# 출처: https://www.zotero.org/support/dev/web_api/v3/basics (Read Requests 표)


def items_path(prefix: str, top: bool = False) -> str:
    """/{prefix}/items 또는 /{prefix}/items/top.

    출처: basics — "<userOrGroupPrefix>/items", "<userOrGroupPrefix>/items/top"
    """
    return f"{prefix}/items/top" if top else f"{prefix}/items"


def item_path(prefix: str, item_key: str) -> str:
    """/{prefix}/items/{itemKey}.

    출처: basics — "<userOrGroupPrefix>/items/<itemKey>"
    """
    return f"{prefix}/items/{item_key}"


def item_children_path(prefix: str, item_key: str) -> str:
    """/{prefix}/items/{itemKey}/children.

    출처: basics — "<userOrGroupPrefix>/items/<itemKey>/children"
    """
    return f"{prefix}/items/{item_key}/children"


def item_fulltext_path(prefix: str, item_key: str) -> str:
    """/{prefix}/items/{itemKey}/fulltext.

    출처: https://www.zotero.org/support/dev/web_api/v3/fulltext_content
    """
    return f"{prefix}/items/{item_key}/fulltext"


def collections_path(prefix: str, top: bool = False) -> str:
    """/{prefix}/collections 또는 /{prefix}/collections/top.

    출처: basics — "<userOrGroupPrefix>/collections", ".../collections/top"
    """
    return f"{prefix}/collections/top" if top else f"{prefix}/collections"


def collection_items_path(prefix: str, collection_key: str) -> str:
    """/{prefix}/collections/{collectionKey}/items.

    출처: basics — "<userOrGroupPrefix>/collections/<collectionKey>/items"
    """
    return f"{prefix}/collections/{collection_key}/items"


def tags_path(prefix: str) -> str:
    """/{prefix}/tags.

    출처: basics — "<userOrGroupPrefix>/tags"
    """
    return f"{prefix}/tags"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 출처: https://www.zotero.org/support/dev/web_api/v3/basics — limit "default 25, max 100".
# (itemKey 최대 50·bib 최대 150 제약은 해당 도구를 추가할 때 상수화 — 현재 MVP 미사용.)
DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# qmode 허용값 — **아이템 quick search 전용**. titleCreatorYear(기본) / everything(전문 포함).
# (태그 엔드포인트는 별도 qmode contains/startsWith를 쓴다 — MVP 범위 밖이라 여기서 다루지 않으며,
#  list_tags는 qmode를 보내지 않는다.)
# 출처: basics — items "qmode" ("titleCreatorYear" 또는 "everything")
QMode = Literal["titleCreatorYear", "everything"]
QMODES: tuple[str, ...] = ("titleCreatorYear", "everything")


def validate_limit(limit: int) -> int:
    """limit를 1..MAX_LIMIT 범위로 검증한다(공식: 기본 25, 최대 100).

    출처: https://www.zotero.org/support/dev/web_api/v3/basics
    """
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit는 1..{MAX_LIMIT} 범위여야 합니다(현재 {limit}).")
    return limit


def build_search_params(
    *,
    q: str | None = None,
    item_type: str | None = None,
    tag: str | None = None,
    qmode: str | None = None,
    sort: str | None = None,
    limit: int = DEFAULT_LIMIT,
    start: int = 0,
) -> dict[str, str | int]:
    """**아이템 검색/리스트** 쿼리스트링을 만든다. None/빈값은 생략한다.

    공식 파라미터명: q · qmode · itemType · tag · sort · limit · start. qmode는 아이템 전용
    (titleCreatorYear/everything). 컬렉션 아이템·태그 리스트는 qmode 없이 limit/start만 쓴다.
    출처: https://www.zotero.org/support/dev/web_api/v3/basics
    """
    validate_limit(limit)
    if qmode is not None and qmode not in QMODES:
        raise ValueError(f"qmode는 {QMODES} 중 하나여야 합니다(현재 {qmode!r}).")
    params: dict[str, str | int] = {"limit": limit, "start": start}
    if q:
        params["q"] = q
    if qmode:
        params["qmode"] = qmode
    if item_type:
        params["itemType"] = item_type  # 공식 카멜케이스 파라미터명
    if tag:
        params["tag"] = tag
    if sort:
        params["sort"] = sort
    return params


# ─── 페이지네이션 헤더 이름(응답 헤더) ──────────────────────
# httpx는 응답 헤더 키를 소문자로 정규화한다 → 소문자 상수로 둔다.
# 출처: basics — "Total-Results" / "Link"(rel=next 등) / "Last-Modified-Version"
#   · "Backoff" / "Retry-After"(429/503)
HDR_TOTAL_RESULTS = "total-results"
HDR_LINK = "link"
HDR_LAST_MODIFIED_VERSION = "last-modified-version"
HDR_BACKOFF = "backoff"
HDR_RETRY_AFTER = "retry-after"


def start_from_next_link(next_url: str | None) -> int | None:
    """`Link: rel=next` URL에서 start 파라미터 값을 뽑아낸다(없으면 None).

    페이지네이션 안내("다음 start=K")에 쓴다. 표준 라이브러리(urllib)만 사용.
    출처: https://www.zotero.org/support/dev/web_api/v3/basics (Link 헤더 기반 페이지네이션)
    """
    if not next_url:
        return None
    from urllib.parse import parse_qs, urlsplit

    qs = parse_qs(urlsplit(next_url).query)
    values = qs.get("start")
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None


# ─── 응답 모델 ──────────────────────────────────────────────
# 최상위 read 응답 오브젝트의 키(key/version/library/links/meta/data)는 공식 Read Requests
# 문서에 일관되게 등장한다. 그러나 library/links/meta **서브객체의 정확한 키**는 공식 산문에서
# 완전히 확인되지 않는다(UNVERIFIED) → extra="ignore"로 느슨히 받고, 확신하는 것만 모델링한다.
# data는 아이템 타입별로 필드가 가변이므로 dict로 둔다.


class ZoteroItem(BaseModel):
    """단일 아이템 read 응답 오브젝트.

    공식 최상위 키: key · version · library · links · meta · data.
    출처: https://www.zotero.org/support/dev/web_api/v3/basics (Read Requests / format=json)

    참고: 공식에 library(type/id/name) · links(rel별 {href,type}) · meta(numChildren/
    creatorSummary/parsedDate 등) 일부 서브키가 명시되나 전수 스키마는 미열거 → dict로 느슨히
    받는다(extra="ignore"). data는 아이템 타입별 가변 필드 → dict.
    # TODO(provenance): 필요 시 library/links/meta 핵심 서브키를 모델로 승격.
    """

    model_config = {"extra": "ignore"}

    key: str
    version: int
    library: dict | None = None  # UNVERIFIED 서브키 → dict
    links: dict | None = None    # UNVERIFIED 서브키 → dict
    meta: dict | None = None     # UNVERIFIED 서브키 → dict
    data: dict | None = None     # 아이템 타입별 가변 필드 → dict


class Collection(BaseModel):
    """단일 컬렉션 read 응답 오브젝트.

    공식 최상위 키: key · version · library · links · meta · data(컬렉션 data는
    name/parentCollection 등). 아이템과 동형 구조.
    출처: https://www.zotero.org/support/dev/web_api/v3/basics (Read Requests)

    UNVERIFIED: 아이템과 동일하게 library/links/meta 서브키 미확정 → dict.
    # TODO(provenance): collection data/meta 서브키 정밀화.
    """

    model_config = {"extra": "ignore"}

    key: str
    version: int
    library: dict | None = None
    links: dict | None = None
    meta: dict | None = None
    data: dict | None = None


class Tag(BaseModel):
    """단일 태그 read 응답 오브젝트.

    공식 최상위 키: tag(태그 문자열) · links · meta. 태그는 key/version/data가 없다.
    출처: https://www.zotero.org/support/dev/web_api/v3/basics (tags 엔드포인트)

    UNVERIFIED: links/meta(예: meta.numItems) 서브키 미확정 → dict.
    # TODO(provenance): tag links/meta 서브키 정밀화(meta.type/numItems 추정 미확인).
    """

    model_config = {"extra": "ignore"}

    tag: str
    links: dict | None = None
    meta: dict | None = None


class Fulltext(BaseModel):
    """전문(full-text) 콘텐츠 응답.

    공식: content는 항상. 텍스트 문서는 indexedChars/totalChars, PDF는
    indexedPages/totalPages를 쓴다("indexedChars and totalChars are used for text
    documents, while indexedPages and totalPages are used for PDFs.").
    출처: https://www.zotero.org/support/dev/web_api/v3/fulltext_content
    """

    model_config = {"extra": "ignore"}

    content: str = ""
    indexedChars: int | None = None  # noqa: N815 (공식 카멜케이스 — 텍스트 문서)
    totalChars: int | None = None    # noqa: N815 (공식 카멜케이스 — 텍스트 문서)
    indexedPages: int | None = None  # noqa: N815 (공식 카멜케이스 — PDF)
    totalPages: int | None = None    # noqa: N815 (공식 카멜케이스 — PDF)


class ErrorResponse(BaseModel):
    """Zotero 에러 응답.

    공식 에러는 본문이 보통 plain text 메시지다(JSON 보장 안 됨). 코어 http는 JSON 파싱
    실패 시 text를 payload로 담으므로, dict로 올 때만 message를 시도한다.
    출처: https://www.zotero.org/support/dev/web_api/v3/basics (에러 응답은 텍스트 메시지)
    # TODO(provenance): JSON 에러 바디 스키마는 공식 산문에 표준화 명시 없음 → 느슨히.
    """

    model_config = {"extra": "ignore"}

    message: str | None = None
