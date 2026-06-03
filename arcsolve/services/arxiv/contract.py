"""arXiv API 학술 프리프린트 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, **Atom 1.0 XML → pydantic 파싱**.
MCP/네트워크 무의존(순수 상수 + pydantic 모델 + 표준 라이브러리 XML 파서).

전부 GET·읽기·**무인증**(키 없음). arXiv는 JSON이 아니라 **Atom 1.0 XML**을 반환하므로
코어 `get_text`(raw str)로 받고 여기서 **표준 라이브러리 `xml.etree.ElementTree`**로 파싱한다
(feedparser/lxml 같은 외부 의존 금지). 페이지네이션/건수는 OpenSearch 확장 요소
(opensearch:totalResults/startIndex/itemsPerPage)에 실린다.

⚠️ 에러 처리: arXiv는 잘못된 입력(malformed id 등)에 **HTTP 200 + 단일 `<entry>` title="Error"**
를 준다. 파서가 이 error-entry를 감지해 ArxivErrorEntry로 매핑한다. (max_results>30000은 HTTP 400.)

출처(공식 문서 — info.arxiv.org):
  - API User Manual(쿼리 인터페이스·파라미터·제약·Atom 응답 구조·error feed·etiquette):
    https://info.arxiv.org/help/api/user-manual.html
  - API 개요(공개 API 안내): https://info.arxiv.org/help/api/index.html
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from pydantic import BaseModel

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base·엔드포인트): User Manual
#   ("The base url for the API is http://export.arxiv.org/api/{method_name}?{parameters}")
#   (HTTP는 코어가 HTTPS로 승격) — query 메서드만 사용(검색/조회 공용).
BASE_URL = "https://export.arxiv.org/api/query"

# ─── XML 네임스페이스(공식) ─────────────────────────────────
# 출처: User Manual 응답 예시의 <feed> 선언
#   xmlns="http://www.w3.org/2005/Atom"
#   xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
#   xmlns:arxiv="http://arxiv.org/schemas/atom"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}

# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 출처: User Manual
#   ("max_results"의 기본 10), ("slice ... in chunks of at most 2000"),
#   ("up to 30000 results"), ("a request with max_results>30000 ... HTTP 400")
DEFAULT_MAX_RESULTS = 10
MAX_RESULTS_PER_REQUEST = 2000  # 1회 요청 권장 상한(공식: 2000 단위로 슬라이스)
MAX_RESULTS_TOTAL = 30000  # 절대 상한 — 초과 시 상류가 HTTP 400

# 공식 파라미터명(정확한 철자 — search_query/id_list는 snake, sortBy/sortOrder는 camel).
# 출처: User Manual ("search_query", "id_list", "start", "max_results", "sortBy", "sortOrder")
PARAM_SEARCH_QUERY = "search_query"
PARAM_ID_LIST = "id_list"
PARAM_START = "start"
PARAM_MAX_RESULTS = "max_results"
PARAM_SORT_BY = "sortBy"
PARAM_SORT_ORDER = "sortOrder"

# sortBy 허용값(공식). 출처: User Manual
#   ("sortBy can be 'relevance', 'lastUpdatedDate', 'submittedDate'")
SORT_RELEVANCE = "relevance"
SORT_LAST_UPDATED = "lastUpdatedDate"
SORT_SUBMITTED = "submittedDate"
VALID_SORT_BY = (SORT_RELEVANCE, SORT_LAST_UPDATED, SORT_SUBMITTED)

# sortOrder 허용값(공식). 출처: User Manual ("sortOrder can be 'ascending' or 'descending'")
ORDER_ASCENDING = "ascending"
ORDER_DESCENDING = "descending"
VALID_SORT_ORDER = (ORDER_ASCENDING, ORDER_DESCENDING)


def validate_max_results(max_results: int) -> int:
    """max_results를 0..30000 범위로 검증한다(공식 절대 상한).

    위반 시 ValueError(상류가 HTTP 400을 주기 전에 미리 막는다).
    출처: User Manual ("a request with max_results>30000 will result in an HTTP 400 error code").
    """
    if max_results < 0 or max_results > MAX_RESULTS_TOTAL:
        raise ValueError(
            f"max_results는 0..{MAX_RESULTS_TOTAL} 범위여야 합니다(현재 {max_results}). "
            f"그 이상은 HTTP 400입니다."
        )
    return max_results


def validate_start(start: int) -> int:
    """start를 0 이상으로 검증한다(0-based 오프셋, 공식).

    출처: User Manual ("start ... defaults to 0" · 0-based index).
    """
    if start < 0:
        raise ValueError(f"start는 0 이상이어야 합니다(현재 {start}).")
    return start


def validate_sort_by(sort_by: str) -> str:
    """sortBy를 relevance/lastUpdatedDate/submittedDate로 검증한다(공식)."""
    if sort_by not in VALID_SORT_BY:
        raise ValueError(f"sort_by는 {VALID_SORT_BY} 중 하나여야 합니다(현재 {sort_by!r}).")
    return sort_by


def validate_sort_order(sort_order: str) -> str:
    """sortOrder를 ascending/descending로 검증한다(공식)."""
    if sort_order not in VALID_SORT_ORDER:
        raise ValueError(
            f"sort_order는 {VALID_SORT_ORDER} 중 하나여야 합니다(현재 {sort_order!r})."
        )
    return sort_order


def build_search_params(
    *,
    search_query: str | None = None,
    id_list: str | None = None,
    start: int | None = None,
    max_results: int | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> dict[str, str | int]:
    """쿼리스트링을 만든다. None/빈값은 생략한다.

    - search_query → `search_query`(필드 prefix `ti/au/abs/co/jr/cat/rn/all` + AND/OR/ANDNOT
      불리언을 **문자열 그대로** 전달. 빌더는 만들지 않는다 — 스코프 밖).
    - id_list → `id_list`(콤마 구분 arXiv id, 선택적 버전 접미사 `v1` 등).
    - start → `start`(0-based 오프셋, 검증).
    - max_results → `max_results`(0..30000 검증).
    - sort_by → `sortBy`(relevance/lastUpdatedDate/submittedDate 검증).
    - sort_order → `sortOrder`(ascending/descending 검증).
    출처: User Manual (search_query·id_list·start·max_results·sortBy·sortOrder).
    """
    params: dict[str, str | int] = {}
    if search_query:
        params[PARAM_SEARCH_QUERY] = search_query
    if id_list:
        params[PARAM_ID_LIST] = id_list
    if start is not None:
        params[PARAM_START] = validate_start(start)
    if max_results is not None:
        params[PARAM_MAX_RESULTS] = validate_max_results(max_results)
    if sort_by is not None:
        params[PARAM_SORT_BY] = validate_sort_by(sort_by)
    if sort_order is not None:
        params[PARAM_SORT_ORDER] = validate_sort_order(sort_order)
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# Atom <feed>는 <entry>* + OpenSearch 메타로 구성된다. extra는 무시하고 확신 필드만 모델링.
# 출처: User Manual 응답 예시(<feed>/<entry> 구조).


class Author(BaseModel):
    """저자(<author>) — <name> + 선택적 <arxiv:affiliation>.

    출처: User Manual ("<author> ... contains a <name> element ... may contain an
    <arxiv:affiliation> element").
    """

    name: str
    affiliation: str | None = None


class Link(BaseModel):
    """링크(<link>) — abstract(rel=alternate)·pdf(title=pdf)·doi(title=doi) 최대 3개.

    출처: User Manual ("link ... rel='alternate' type='text/html'"(abstract) ·
    "title='pdf'"(pdf) · "title='doi'"(doi)).
    """

    href: str
    rel: str | None = None
    title: str | None = None
    type: str | None = None


class Category(BaseModel):
    """분류(<category term scheme>) — arXiv/ACM/MSC.

    출처: User Manual ("<category> ... 'term' ... 'scheme'").
    """

    term: str
    scheme: str | None = None


class ArxivEntry(BaseModel):
    """단일 프리프린트(<entry>) — 부분 모델.

    필드(공식): id(abs URL) · title · summary(초록) · authors([{name,affiliation}]) ·
    published(v1 제출일) · updated(조회 버전 제출일) · categories([{term,scheme}]) ·
    primary_category(arxiv:primary_category term) · links(abstract/pdf/doi 최대 3) ·
    comment(arxiv:comment) · journal_ref(arxiv:journal_ref) · doi(arxiv:doi).
    출처: User Manual 응답 예시(<entry> 하위 요소).
    """

    id: str
    title: str
    summary: str | None = None
    authors: list[Author] = []
    published: str | None = None
    updated: str | None = None
    categories: list[Category] = []
    primary_category: str | None = None
    links: list[Link] = []
    comment: str | None = None
    journal_ref: str | None = None
    doi: str | None = None


class ArxivFeed(BaseModel):
    """검색/조회 응답 피드(<feed>) — 부분 모델.

    OpenSearch 메타(total_results/start_index/items_per_page) + entries.
    출처: User Manual ("<opensearch:totalResults>" · "<opensearch:startIndex>" ·
    "<opensearch:itemsPerPage>").
    """

    total_results: int | None = None
    start_index: int | None = None
    items_per_page: int | None = None
    entries: list[ArxivEntry] = []


class ArxivErrorEntry(BaseModel):
    """arXiv error-entry(HTTP 200 + 단일 <entry> title='Error').

    잘못된 입력(malformed id 등)에 상류가 200으로 주는 에러 피드. <id>는 에러 설명 URL
    (`http://arxiv.org/api/errors#...`), <summary>가 사람이 읽을 메시지.
    출처: User Manual ("Errors are returned ... a single Atom entry ... <title>Error</title>
    ... the <summary> ... contains a ... error message" · id가 errors# URL).
    """

    summary: str
    id: str | None = None


# ─── XML → 모델 파싱 ────────────────────────────────────────


def _text(el: ET.Element | None) -> str | None:
    """요소 텍스트를 trim해 돌려준다(없으면 None). 빈 문자열도 None."""
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def _normalize_ws(text: str | None) -> str | None:
    """title/summary의 줄바꿈·연속 공백을 한 칸으로 정리한다(arXiv는 본문을 줄바꿈해 넣음)."""
    if text is None:
        return None
    return " ".join(text.split()) or None


ERROR_TITLE = "Error"
# 출처: User Manual — error-entry의 <id>는 `http://arxiv.org/api/errors#...` 형태.
_ERROR_ID_MARKER = "/api/errors"


def is_error_feed(root: ET.Element) -> bool:
    """피드가 arXiv error-entry인지 감지한다.

    감지 규칙: <entry>가 정확히 1개이고 그 <title>이 'Error'이며 <id>가 errors# URL이다
    (정상 entry의 id는 `.../abs/...`라 errors 마커가 없으므로, title='Error'와 id 마커를
    함께 확인해 오탐을 막는다 — 제목이 우연히 'Error'인 정상 논문 보호).
    출처: User Manual (error feed = single entry, title 'Error', id errors# URL).
    """
    entries = root.findall("atom:entry", NS)
    if len(entries) != 1:
        return False
    e = entries[0]
    title = _text(e.find("atom:title", NS))
    if title != ERROR_TITLE:
        return False
    eid = _text(e.find("atom:id", NS)) or ""
    return _ERROR_ID_MARKER in eid


def parse_error_entry(root: ET.Element) -> ArxivErrorEntry:
    """error-entry 피드에서 ArxivErrorEntry를 만든다(is_error_feed가 True일 때 호출).

    <summary>(사람이 읽을 에러 메시지) + <id>(에러 설명 URL).
    """
    e = root.findall("atom:entry", NS)[0]
    summary = _text(e.find("atom:summary", NS)) or "arXiv API 에러"
    return ArxivErrorEntry(summary=summary, id=_text(e.find("atom:id", NS)))


def _parse_entry(e: ET.Element) -> ArxivEntry:
    """단일 <entry> 요소를 ArxivEntry로 파싱한다."""
    authors: list[Author] = []
    for a in e.findall("atom:author", NS):
        name = _text(a.find("atom:name", NS))
        if name is None:
            continue
        authors.append(Author(name=name, affiliation=_text(a.find("arxiv:affiliation", NS))))

    links: list[Link] = []
    for ln in e.findall("atom:link", NS):
        href = ln.get("href")
        if not href:
            continue
        links.append(
            Link(href=href, rel=ln.get("rel"), title=ln.get("title"), type=ln.get("type"))
        )

    categories: list[Category] = []
    for cat in e.findall("atom:category", NS):
        term = cat.get("term")
        if term:
            categories.append(Category(term=term, scheme=cat.get("scheme")))

    prim = e.find("arxiv:primary_category", NS)
    primary_category = prim.get("term") if prim is not None else None

    return ArxivEntry(
        id=_text(e.find("atom:id", NS)) or "",
        title=_normalize_ws(_text(e.find("atom:title", NS))) or "(제목 없음)",
        summary=_normalize_ws(_text(e.find("atom:summary", NS))),
        authors=authors,
        published=_text(e.find("atom:published", NS)),
        updated=_text(e.find("atom:updated", NS)),
        categories=categories,
        primary_category=primary_category,
        links=links,
        comment=_text(e.find("arxiv:comment", NS)),
        journal_ref=_text(e.find("arxiv:journal_ref", NS)),
        doi=_text(e.find("arxiv:doi", NS)),
    )


def _parse_int(el: ET.Element | None) -> int | None:
    """OpenSearch 정수 요소를 int로 파싱한다(없거나 비정수면 None)."""
    t = _text(el)
    if t is None:
        return None
    try:
        return int(t)
    except ValueError:
        return None


def parse_feed(xml_text: str) -> ArxivFeed | ArxivErrorEntry:
    """Atom 1.0 XML 문자열을 ArxivFeed로 파싱한다.

    error-entry(HTTP 200 + title='Error')면 ArxivErrorEntry를 돌려준다 → 호출부가 분기.
    XML이 깨졌으면 ET.ParseError가 올라간다(호출부가 매핑).
    출처: User Manual 응답 구조 + error feed 규칙.
    """
    root = ET.fromstring(xml_text)
    if is_error_feed(root):
        return parse_error_entry(root)
    return ArxivFeed(
        total_results=_parse_int(root.find("opensearch:totalResults", NS)),
        start_index=_parse_int(root.find("opensearch:startIndex", NS)),
        items_per_page=_parse_int(root.find("opensearch:itemsPerPage", NS)),
        entries=[_parse_entry(e) for e in root.findall("atom:entry", NS)],
    )
