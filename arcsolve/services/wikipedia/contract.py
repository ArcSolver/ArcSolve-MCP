"""Wikipedia(위키백과) 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 호스트/경로 상수, 언어·limit 검증, 제목 인코더, HTML 스트립
헬퍼, 부분 응답 모델. MCP/네트워크 무의존(순수 상수 + 헬퍼 + pydantic 모델).

전부 GET·읽기. **무인증**(키 없음)으로 전체 읽기가 동작하지만, Wikimedia는 NWS처럼 식별용
**`User-Agent` 헤더를 요구**한다(없거나 약하면 403/스로틀). 기본 식별 문자열을
`DEFAULT_USER_AGENT` 상수로 두고 tools에서 env(`WIKIPEDIA_USER_AGENT`)로 덮어쓴다. (선택)
Bearer 토큰을 주면 레이트리밋이 완화되지만 토큰 없이도 읽기는 전부 동작한다.

언어판마다 호스트가 다르다: `https://{lang}.wikipedia.org`. 세 종류의 엔드포인트를 섞어 쓴다.
  - 검색: per-wiki REST  `/w/rest.php/v1/search/page`  (구식 Action API `list=search`가 아님)
  - 요약: rest_v1        `/api/rest_v1/page/summary/{title}`  (lead extract; 2026년 현재 살아있음)
  - 본문: Action API     `/w/api.php?action=query&prop=extracts` (TextExtracts 확장)
  - 링크: Action API     `/w/api.php?action=query&prop=links|categories`
⚠️ `api.wikimedia.org/core/v1/*`(통합 REST)는 2026-07 deprecation 예정·후속 없음 → 사용하지 않는다.

출처(공식 문서 + 라이브 확인):
  - per-wiki REST(검색) 레퍼런스: https://www.mediawiki.org/wiki/API:REST_API/Reference
  - rest_v1(summary) — Wikimedia REST API: https://www.mediawiki.org/wiki/Wikimedia_REST_API
    (per-wiki rest_v1 명세: https://en.wikipedia.org/api/rest_v1/)
  - TextExtracts(prop=extracts·exintro·explaintext·exchars): https://www.mediawiki.org/wiki/Extension:TextExtracts
  - Action API(query·prop=links|categories·formatversion=2·redirects): https://www.mediawiki.org/wiki/API:Query
  - 라이브 응답 확인: /w/rest.php/v1/search/page · /api/rest_v1/page/summary/{title} ·
    /w/api.php?action=query&prop=extracts · /w/api.php?action=query&prop=links|categories
"""

from __future__ import annotations

import re
from urllib.parse import quote

from pydantic import BaseModel

# ─── 호스트 / 경로 상수 ─────────────────────────────────────
# 언어판마다 호스트가 다르다(예: en·ko·de·zh·simple). base는 wiki_host(lang)로 만든다.
# 출처(per-wiki REST·Action API base): API:REST_API/Reference, API:Main_page(`/w/api.php`) + 라이브.
SCHEME = "https"
WIKI_HOST_SUFFIX = "wikipedia.org"

# per-wiki REST 검색(클린 REST — 폐기 대상 아님). 출처: API:REST_API/Reference(Search pages) + 라이브.
REST_SEARCH_PATH = "/w/rest.php/v1/search/page"
# rest_v1 요약(lead extract; 리다이렉트 자동 추적). 출처: Wikimedia_REST_API + 라이브(/page/summary/{title}).
REST_V1_SUMMARY_PREFIX = "/api/rest_v1/page/summary/"
# Action API 엔드포인트(TextExtracts·links/categories). 출처: API:Query + 라이브(/w/api.php).
ACTION_API_PATH = "/w/api.php"


# ─── User-Agent (필수) ──────────────────────────────────────
# Wikimedia는 식별용 User-Agent를 요구한다(약하거나 없으면 403/스로틀). NWS와 동일 패턴으로 기본
# 식별 문자열을 상수로 두고 env로 덮어쓴다. 출처: Wikimedia User-Agent policy + NWS 동형.
DEFAULT_USER_AGENT = "ArcSolve-MCP (github.com/ArcSolver/ArcSolve-MCP)"


def wiki_host(lang: str) -> str:
    """언어판 base URL `https://{lang}.wikipedia.org`를 만든다(검증된 lang 가정).

    출처: per-wiki 호스트 규칙(예: en.wikipedia.org·ko.wikipedia.org) + 라이브.
    """
    return f"{SCHEME}://{lang}.{WIKI_HOST_SUFFIX}"


def summary_path(title: str) -> str:
    """rest_v1 요약 경로 `/api/rest_v1/page/summary/{title}`.

    title은 path segment이므로 `quote(safe="")`로 슬래시·공백까지 전부 인코딩한다(`%20`·`%2F`).
    rest_v1은 리다이렉트를 자동 추적한다(라이브: NYC → New York City).
    출처: Wikimedia_REST_API(/page/summary/{title}) + 라이브.
    """
    return f"{REST_V1_SUMMARY_PREFIX}{encode_title(title)}"


# ─── 제목 인코더 ────────────────────────────────────────────


def encode_title(title: str) -> str:
    """rest_v1 path segment용 제목 인코딩(공백·슬래시 포함 전부).

    `urllib.parse.quote(title, safe="")` — path segment라 `/`도 인코딩해야 한다(`%2F`).
    Action API의 `titles=`는 쿼리 파라미터라 별도 인코딩 불필요(httpx가 처리) → 거기엔 쓰지 않는다.
    """
    return quote(title.strip(), safe="")


# ─── 언어 / limit 검증 ──────────────────────────────────────
# lang은 위키 서브도메인(언어 코드)이다. 가볍게 검증한다: 소문자 + [a-z-] (예: en·ko·de·zh·simple·
# zh-yue). 숫자/대문자/언더스코어는 거른다(SSRF·오타 방지). 모든 코드를 enum으로 박지는 않는다
# (위키 언어판이 300+이고 추가/변경됨) — 형식 검증만.
# 출처: per-wiki 언어 서브도메인 규칙(소문자 ISO 639 코드 + 하이픈 변형).
LANG_RE = re.compile(r"^[a-z]+(-[a-z]+)*$")
DEFAULT_LANG = "en"

# REST 검색 limit: 1..100(기본 10). 출처: API:REST_API/Reference(Search pages — limit 1–100, 기본 50).
MIN_LIMIT = 1
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 100
# Action API links/categories pllimit·cllimit 상한(비-bot은 500). 출처: API:Links/API:Categories.
DEFAULT_LINKS_LIMIT = 50
MAX_LINKS_LIMIT = 500
# TextExtracts exchars 상한 1200(확장 한도). 출처: Extension:TextExtracts(exchars max 1200).
MIN_EXCHARS = 1
MAX_EXCHARS = 1200


def validate_lang(lang: str) -> str:
    """lang을 소문자 언어 코드(`[a-z]`+하이픈 변형)로 정규화·검증한다.

    소문자로 맞추고 형식만 본다(예: `en`·`ko`·`de`·`zh`·`simple`·`zh-yue`). 형식 위반은
    HTTP 전에 막는다(호스트 오염·오타 방지). 출처: per-wiki 언어 서브도메인 규칙.
    """
    code = lang.strip().lower()
    if not code or not LANG_RE.match(code):
        raise ValueError(
            f"lang은 소문자 언어 코드여야 합니다(현재 {lang!r}). 예: en, ko, de, zh, simple."
        )
    return code


def validate_limit(limit: int, *, maximum: int) -> int:
    """limit을 1..maximum 범위로 검증한다(검색=100·링크=500).

    위반 시 ValueError(상류 호출 전에 막는다).
    출처: API:REST_API/Reference(search limit 1–100), API:Links/API:Categories(pllimit/cllimit ≤500).
    """
    if limit < MIN_LIMIT or limit > maximum:
        raise ValueError(f"limit은 {MIN_LIMIT}..{maximum} 범위여야 합니다(현재 {limit}).")
    return limit


def validate_exchars(max_chars: int) -> int:
    """exchars(요약 글자 수)를 1..1200 범위로 검증한다.

    위반 시 ValueError. 출처: Extension:TextExtracts(exchars 상한 1200).
    """
    if max_chars < MIN_EXCHARS or max_chars > MAX_EXCHARS:
        raise ValueError(
            f"max_chars는 {MIN_EXCHARS}..{MAX_EXCHARS} 범위여야 합니다(현재 {max_chars})."
        )
    return max_chars


# ─── HTML 태그 스트립 헬퍼 ──────────────────────────────────
# REST 검색의 `excerpt`는 `<span class="searchmatch">…</span>` 같은 HTML 스니펫이다(라이브 확인).
# 평문 한 줄로 보여주기 위해 태그를 지우고 HTML 엔티티 일부를 푼다(표준 html.unescape 사용).
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(snippet: str | None) -> str:
    """HTML 스니펫에서 태그를 제거하고 공백을 정리한 평문을 돌려준다.

    `<span class="searchmatch">…</span>` 등의 태그를 지우고, 엔티티(`&#039;`·`&amp;` 등)를
    `html.unescape`로 푼다. None/빈값이면 빈 문자열. 출처: 라이브(REST 검색 excerpt = HTML 스니펫).
    """
    if not snippet:
        return ""
    import html

    text = _TAG_RE.sub("", snippet)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


# ─── 쿼리 파라미터 빌더 (Action API) ───────────────────────
# Action API는 항상 format=json·formatversion=2를 쓴다. formatversion=2면 query.pages가
# pageid-keyed 객체가 아니라 **깨끗한 배열**로 온다(라이브 확인). redirects=1로 리다이렉트를 따른다.
# 출처: API:JSON_version_2(formatversion=2), API:Query(redirects), Extension:TextExtracts.


def extracts_params(
    title: str, *, intro_only: bool = True, max_chars: int | None = None
) -> dict[str, str | int]:
    """TextExtracts 평문 본문 쿼리스트링을 만든다(prop=extracts).

    explaintext=1(평문)·formatversion=2(배열)·redirects=1(리다이렉트 추적). intro_only면
    exintro=1(도입부만), max_chars면 exchars={n}(글자 수 제한). titles는 쿼리 파라미터라 별도
    인코딩하지 않는다(httpx가 처리). 출처: Extension:TextExtracts + 라이브.
    """
    params: dict[str, str | int] = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "format": "json",
        "formatversion": 2,
        "redirects": 1,
        "titles": title,
    }
    if intro_only:
        params["exintro"] = 1
    if max_chars is not None:
        params["exchars"] = max_chars
    return params


def links_params(title: str, *, limit: int = DEFAULT_LINKS_LIMIT) -> dict[str, str | int]:
    """나가는 링크 + 분류 쿼리스트링을 만든다(prop=links|categories).

    plnamespace=0(문서 네임스페이스 링크만)·pllimit/cllimit={limit}·formatversion=2·redirects=1.
    출처: API:Links(plnamespace·pllimit), API:Categories(cllimit) + 라이브.
    """
    return {
        "action": "query",
        "prop": "links|categories",
        "titles": title,
        "plnamespace": 0,
        "pllimit": limit,
        "cllimit": limit,
        "format": "json",
        "formatversion": 2,
        "redirects": 1,
    }


# ─── 응답 모델 (부분 모델 · extra="ignore") ────────────────
# fields가 빠질 수 있어 핵심 외 전부 Optional. snake_case와 다른 상류 키만 alias.


class SearchThumbnail(BaseModel):
    """REST 검색 결과의 `thumbnail`(부분). url은 `//upload...`처럼 scheme-relative일 수 있다.

    출처: 라이브(/w/rest.php/v1/search/page → pages[].thumbnail{url,width,height,mimetype}).
    """

    model_config = {"extra": "ignore"}

    url: str | None = None
    width: int | None = None
    height: int | None = None


class SearchPage(BaseModel):
    """REST 검색 결과 `pages[]` 한 항목(부분).

    id·key(URL 슬러그)·title·excerpt(HTML 스니펫)·matched_title·description·thumbnail.
    REST 검색 응답에는 total 필드가 **없다**(라이브 확인). 출처: API:REST_API/Reference + 라이브.
    """

    model_config = {"extra": "ignore"}

    id: int | None = None
    key: str | None = None
    title: str | None = None
    excerpt: str | None = None
    matched_title: str | None = None
    description: str | None = None
    thumbnail: SearchThumbnail | None = None


class SearchResponse(BaseModel):
    """REST 검색 응답 봉투 `{"pages":[...]}`(total 없음).

    출처: 라이브(/w/rest.php/v1/search/page → {"pages":[...]}).
    """

    model_config = {"extra": "ignore"}

    pages: list[SearchPage] = []


class SummaryContentUrls(BaseModel):
    """rest_v1 요약의 `content_urls.desktop.page`만 뽑기 위한 중첩 모델(부분).

    출처: 라이브(/api/rest_v1/page/summary → content_urls.desktop.page).
    """

    model_config = {"extra": "ignore"}

    class _Desktop(BaseModel):
        model_config = {"extra": "ignore"}

        page: str | None = None

    desktop: _Desktop | None = None


class SummaryThumbnail(BaseModel):
    """rest_v1 요약의 `thumbnail`(부분) — 대표 이미지 `source` URL.

    출처: 라이브(/api/rest_v1/page/summary → thumbnail.source).
    """

    model_config = {"extra": "ignore"}

    source: str | None = None


class SummaryCoordinates(BaseModel):
    """rest_v1 요약의 `coordinates`(부분) — 지리 문서일 때만 존재.

    출처: 라이브(/api/rest_v1/page/summary/Paris → coordinates{lat,lon}).
    """

    model_config = {"extra": "ignore"}

    lat: float | None = None
    lon: float | None = None


class SummaryResponse(BaseModel):
    """rest_v1 요약 응답 최상위(부분).

    type(`standard`·`disambiguation` 등)·title·description·extract·content_urls.desktop.page·
    thumbnail.source·lang·**wikibase_item**(Wikidata Q-id 브리지)·coordinates(지리일 때).
    404면 상류가 4xx → tools에서 "문서를 찾을 수 없습니다"로 매핑(여기선 모델만).
    출처: 라이브(/api/rest_v1/page/summary/{title}) + Wikimedia_REST_API.
    """

    model_config = {"extra": "ignore"}

    type: str | None = None
    title: str | None = None
    description: str | None = None
    extract: str | None = None
    lang: str | None = None
    wikibase_item: str | None = None
    content_urls: SummaryContentUrls | None = None
    thumbnail: SummaryThumbnail | None = None
    coordinates: SummaryCoordinates | None = None


class ExtractPage(BaseModel):
    """TextExtracts `query.pages[]` 한 항목(formatversion=2 배열, 부분).

    존재하면 {pageid,title,extract}, 없으면 {title,missing:true}. missing이 True면 문서 없음.
    출처: 라이브(action=query&prop=extracts&formatversion=2 → query.pages[]).
    """

    model_config = {"extra": "ignore"}

    pageid: int | None = None
    title: str | None = None
    extract: str | None = None
    missing: bool | None = None


class LinkItem(BaseModel):
    """`query.pages[0].links[]` 한 항목 {ns,title}(부분).

    출처: 라이브(prop=links&plnamespace=0 → links[]{ns,title}).
    """

    model_config = {"extra": "ignore"}

    ns: int | None = None
    title: str | None = None


class CategoryItem(BaseModel):
    """`query.pages[0].categories[]` 한 항목 {ns,title}(부분). title은 `Category:`/`분류:` 접두 포함.

    출처: 라이브(prop=categories → categories[]{ns,title}).
    """

    model_config = {"extra": "ignore"}

    ns: int | None = None
    title: str | None = None


class LinksPage(BaseModel):
    """links/categories 조회의 `query.pages[0]`(부분). links·categories는 둘 다 없을 수 있다.

    missing=true면 문서 없음(extracts와 동일). 출처: 라이브(prop=links|categories → query.pages[0]).
    """

    model_config = {"extra": "ignore"}

    pageid: int | None = None
    title: str | None = None
    missing: bool | None = None
    links: list[LinkItem] = []
    categories: list[CategoryItem] = []


class ActionError(BaseModel):
    """Action API 에러 봉투 `{"error":{"code","info"}}`(부분).

    ⚠️ Action API는 잘못된 파라미터에 **HTTP 200 + 본문 error**를 줄 수 있다(4xx가 아님, 라이브
    확인: action=nonsense·exchars=abc). tools에서 본문을 보고 매핑한다.
    출처: 라이브(/w/api.php?action=nonsense → {"error":{"code":"badvalue","info":...}}).
    """

    model_config = {"extra": "ignore"}

    code: str | None = None
    info: str | None = None
