"""arXiv API 학술 프리프린트 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기·**무인증**(키 없음).
arXiv는 Atom 1.0 XML을 반환하므로 코어 `get_text`(raw str)로 받고 contract.parse_feed로
표준 라이브러리 파싱한다. 페이지네이션/건수는 본문 OpenSearch 메타에 실린다.
인터랙티브 OAuth가 아니므로 make_auth_client 없음(crossref/openalex와 동형).

⚠️ error-entry: arXiv는 잘못된 입력(malformed id 등)에 HTTP 200 + title='Error' 피드를 준다.
parse_feed가 ArxivErrorEntry로 매핑하므로 도구는 그 분기를 깔끔한 메시지로 노출한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import ParseError

from arcsolve.http import UpstreamError, get_text
from arcsolve.services.arxiv import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


def _user_agent() -> dict[str, str]:
    """식별용 User-Agent 헤더(무인증이지만 식별은 예의).

    출처: API index — 공개 API 식별 권장.
    """
    return {"User-Agent": "ArcSolve-MCP/arxiv (https://github.com/ArcSolver/ArcSolve-Kit)"}


def _explain(e: UpstreamError) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    arXiv는 잘못된 입력 대부분을 HTTP 200 error-entry로 주므로(파서가 처리) HTTP 에러는
    드물다. max_results>30000은 400, 그 외 5xx는 서버 부하/일시 장애다.
    출처: User Manual ("max_results>30000 ... HTTP 400").
    """
    if e.status == 400:
        return (
            "요청 오류(400): 파라미터를 확인하세요. "
            f"max_results는 0..{c.MAX_RESULTS_TOTAL} 범위여야 합니다."
        )
    if e.status == 503:
        return "서비스 일시 불가(503): arXiv 서버가 바쁩니다. 잠시 후 재시도하세요."
    return f"arXiv API 오류 {e.status}: {e.payload}"


def _authors(entry: c.ArxivEntry) -> str:
    """저자 목록에서 '첫 저자 외 N명' 형태의 짧은 요약을 만든다."""
    if not entry.authors:
        return "(저자 없음)"
    first = entry.authors[0].name
    extra = len(entry.authors) - 1
    return f"{first} 외 {extra}명" if extra > 0 else first


def _arxiv_id(entry: c.ArxivEntry) -> str:
    """abs URL(<id>)에서 짧은 arXiv id를 뽑는다(예: .../abs/1605.08386v1 → 1605.08386v1)."""
    marker = "/abs/"
    idx = entry.id.find(marker)
    return entry.id[idx + len(marker):] if idx >= 0 else entry.id


def _year(entry: c.ArxivEntry) -> str:
    """published(ISO 8601, 예: 2015-05-01T...)에서 연도만 뽑는다. 없으면 '?'."""
    if entry.published and len(entry.published) >= 4:
        return entry.published[:4]
    return "?"


def _pdf_url(entry: c.ArxivEntry) -> str | None:
    """links에서 PDF 링크(title='pdf')의 href를 찾는다. 없으면 None."""
    for ln in entry.links:
        if ln.title == "pdf":
            return ln.href
    return None


def _entry_line(entry: c.ArxivEntry) -> str:
    """검색 결과 1줄: `- [id] (year) title — 첫 저자 외`."""
    return f"- [{_arxiv_id(entry)}] ({_year(entry)}) {entry.title} — {_authors(entry)}"


def _feed_note(feed: c.ArxivFeed) -> str:
    """피드 OpenSearch 메타로 '총 N건' 안내 문자열을 만든다."""
    total = feed.total_results if feed.total_results is not None else "?"
    return f"총 {total}건"


async def _fetch_feed(params: dict) -> c.ArxivFeed | c.ArxivErrorEntry | str:
    """공통: get_text로 XML을 받아 parse_feed한다. 에러는 사람이 읽을 str로 돌려준다.

    반환:
      - ArxivFeed: 정상 피드
      - ArxivErrorEntry: arXiv error-entry(HTTP 200 + title='Error')
      - str: HTTP/파싱 에러 메시지(호출부가 그대로 노출)
    """
    try:
        xml = await get_text(c.BASE_URL, params=params, headers=_user_agent())
    except UpstreamError as e:
        return _explain(e)
    try:
        return c.parse_feed(xml)
    except ParseError:
        return "응답 파싱 실패: arXiv가 올바른 Atom XML을 반환하지 않았습니다."


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def arxiv_search(
        query: str,
        start: int = 0,
        max_results: int = c.DEFAULT_MAX_RESULTS,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> str:
        """arXiv에서 학술 프리프린트를 검색한다(GET /api/query, search_query).

        Args:
            query: `search_query` 문자열(그대로 전달). 필드 prefix를 붙일 수 있다 —
                `ti:`(제목) `au:`(저자) `abs:`(초록) `cat:`(분류) `all:`(전체).
                불리언 `AND`/`OR`/`ANDNOT`로 결합. 예: `ti:electron AND au:hooft`,
                `cat:cs.AI`. prefix가 없으면 `all:`처럼 전반 검색된다.
            start: 결과 시작 오프셋(0부터). 페이지네이션용.
            max_results: 가져올 개수. 기본 10, 0..30000(1회 2000 이하 권장).
            sort_by: 정렬 기준 `relevance`/`lastUpdatedDate`/`submittedDate`.
            sort_order: 정렬 방향 `ascending`/`descending`.
        """
        try:
            params = c.build_search_params(
                search_query=query, start=start, max_results=max_results,
                sort_by=sort_by, sort_order=sort_order,
            )
        except ValueError as e:  # 범위/열거 위반은 HTTP 전에 막힌다
            return str(e)

        result = await _fetch_feed(params)
        if isinstance(result, str):
            return result
        if isinstance(result, c.ArxivErrorEntry):
            return f"arXiv 오류: {result.summary}"
        note = _feed_note(result)
        if not result.entries:
            return f"검색 결과 없음. ({note})"
        return note + "\n" + "\n".join(_entry_line(e) for e in result.entries)

    @mcp.tool
    async def arxiv_get(id_list: str) -> str:
        """arXiv id로 프리프린트 메타데이터를 조회한다(GET /api/query, id_list).

        단건이면 상세(제목·저자·초록·분류·날짜·PDF·코멘트·저널·DOI), 다건이면 한 줄 요약 목록.

        Args:
            id_list: 콤마로 구분한 arXiv id 목록(예: `1605.08386`,
                `cond-mat/0207270v1`). 버전 접미사(`v1` 등)는 선택. malformed id는 arXiv가
                HTTP 200 error-entry로 응답하며 이 도구가 깔끔히 매핑한다.
        """
        if not id_list or not id_list.strip():
            return "id_list가 비어 있습니다. arXiv id를 콤마로 구분해 입력하세요."

        params = c.build_search_params(id_list=id_list.strip())
        result = await _fetch_feed(params)
        if isinstance(result, str):
            return result
        if isinstance(result, c.ArxivErrorEntry):
            return f"arXiv 오류: {result.summary}"
        if not result.entries:
            return "결과 없음. id_list의 arXiv id를 확인하세요."
        if len(result.entries) > 1:
            return f"총 {len(result.entries)}건\n" + "\n".join(
                _entry_line(e) for e in result.entries
            )

        # 단건 상세
        e = result.entries[0]
        lines = [
            f"[{_arxiv_id(e)}] ({_year(e)}) {e.title}",
            f"- 저자: {_authors(e)}",
        ]
        if e.primary_category:
            cats = ", ".join(cat.term for cat in e.categories) or e.primary_category
            lines.append(f"- 분류: {e.primary_category} ({cats})")
        if e.published:
            lines.append(f"- 제출: {e.published}" + (f" · 갱신 {e.updated}" if e.updated else ""))
        pdf = _pdf_url(e)
        if pdf:
            lines.append(f"- PDF: {pdf}")
        if e.doi:
            lines.append(f"- DOI: {e.doi}")
        if e.journal_ref:
            lines.append(f"- 저널: {e.journal_ref}")
        if e.comment:
            lines.append(f"- 코멘트: {e.comment}")
        if e.summary:
            lines.append(f"- 초록: {e.summary}")
        return "\n".join(lines)
