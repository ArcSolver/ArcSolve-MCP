"""Crossref REST API 학술 메타데이터 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

**무인증**(키 없음). polite pool 이메일(`mailto`)은 헤더가 아니라 **쿼리 파라미터**다 →
contract.build_params가 params에 넣는다(추가로 식별용 User-Agent에도 명시 — 공식 etiquette 권장).
페이지네이션/건수는 응답 **본문 message**(total-results 등)에 실리므로 코어 `get_json`만 쓴다.
인터랙티브 OAuth가 아니므로 make_auth_client 없음(openalex/zotero와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.crossref import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class CrossrefSettings(BaseSettings):
    """CROSSREF_* 환경변수에서 (선택) polite pool 이메일을 로드한다.

    - mailto: polite pool 연락 이메일(선택). 있으면 쿼리 `mailto=`로 보내고 User-Agent에도 명시한다.
    없어도 동작한다(public pool, 무인증).
    """

    model_config = SettingsConfigDict(env_prefix="CROSSREF_", env_file=".env", extra="ignore")
    mailto: str | None = None


def _user_agent(mailto: str | None) -> dict[str, str]:
    """식별용 User-Agent 헤더. mailto가 있으면 공식 etiquette대로 `(mailto:...)`를 덧붙인다.

    출처: README ("Include a 'mailto:' in your User-Agent header") — polite pool 식별.
    """
    ua = "ArcSolve-MCP/crossref (https://github.com/ArcSolver/ArcSolve-Kit)"
    if mailto:
        ua += f" (mailto:{mailto})"
    return {"User-Agent": ua}


def _explain(e: UpstreamError) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    Crossref validation-failure 봉투는 JSON일 때 `{status, message:[{message,...}]}` —
    message 배열의 첫 항목 텍스트만 노출한다. 404(없는 DOI/ISSN)는 본문이 text/plain
    `Resource not found.`이므로 dict가 아니면 detail을 비워 원문 오염을 막는다.
    출처: 라이브 (/works?rows=1001 → 400 validation-failure / /works/<bad> → 404 text/plain)
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        m = payload.get("message")
        if isinstance(m, list) and m and isinstance(m[0], dict):
            msg = m[0].get("message")
        elif isinstance(m, str):
            msg = m
    detail = f" {msg.strip()}" if msg else ""  # 비-JSON(text/plain) 본문은 노출하지 않음
    if e.status == 400:
        return f"요청 오류(400): query/filter/sort/order/rows/offset을 확인하세요.{detail}"
    if e.status == 404:
        return "찾을 수 없음(404): DOI 또는 ISSN을 확인하세요."
    if e.status == 429:
        return (
            "요청 한도 초과(429): 잠시 후 재시도하세요. "
            f"CROSSREF_MAILTO로 polite pool을 쓰면 안정적입니다.{detail}"
        )
    if e.status == 504:
        return f"게이트웨이 시간초과(504): 쿼리가 무겁습니다. rows를 줄이거나 재시도하세요.{detail}"
    return f"Crossref API 오류 {e.status}:{detail or ' ' + str(e.payload)}"


def _authors(authors: list[dict] | None) -> str:
    """author 배열에서 '첫 저자 외 N명' 형태의 짧은 요약을 만든다(given/family 결합)."""
    if not authors:
        return "(저자 없음)"
    first = authors[0]
    given = (first.get("given") or "").strip()
    family = (first.get("family") or "").strip()
    name = f"{given} {family}".strip() or first.get("name") or "(이름 없음)"
    extra = len(authors) - 1
    return f"{name} 외 {extra}명" if extra > 0 else name


def _year(published: dict | None) -> str:
    """published({date-parts:[[Y,M,D]]})에서 연도만 뽑는다. 없으면 '?'."""
    if not published:
        return "?"
    parts = published.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        return str(parts[0][0])
    return "?"


def _title(titles: list[str] | None) -> str:
    """title 배열의 첫 항목. 없으면 '(제목 없음)'."""
    return titles[0] if titles else "(제목 없음)"


def _work_line(w: c.Work) -> str:
    """검색 결과 1줄: `- [DOI] (year) title — 첫 저자 외`."""
    return f"- [{w.doi or '?'}] ({_year(w.published)}) {_title(w.title)} — {_authors(w.author)}"


def _list_note(msg: c.ListMessage) -> str:
    """리스트 응답 message로 '총 N건' 안내 문자열을 만든다."""
    total = msg.total_results if msg.total_results is not None else "?"
    return f"총 {total}건"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def crossref_search_works(
        query: str | None = None,
        filter: str | None = None,  # noqa: A002 (공식 파라미터명 "filter")
        sort: str | None = None,
        order: str | None = None,
        rows: int = c.DEFAULT_ROWS,
        offset: int = 0,
    ) -> str:
        """Crossref에서 학술 출판물(works)을 검색/나열한다(GET /works).

        Args:
            query: 자유 전문 검색어. 미지정 시 필터/정렬만으로 나열한다.
            filter: 필터식 `name:value`(콤마=AND). 예: `type:journal-article`,
                `from-pub-date:2020-01-01`, `has-abstract:true`.
            sort: 정렬 필드(예: `is-referenced-by-count`, `published`, `relevance`, `score`).
            order: 정렬 방향 `asc`/`desc`.
            rows: 페이지 크기. 기본 20, 0..1000.
            offset: 시작 오프셋(0부터). 0..10000(그 이상은 cursor 필요 — 범위 밖).
        """
        s = CrossrefSettings()
        try:
            params = c.build_params(
                query=query, filter=filter, sort=sort, order=order,
                rows=rows, offset=offset, mailto=s.mailto,
            )
        except ValueError as e:  # rows/offset 범위·order 위반은 HTTP 전에 막힌다
            return str(e)

        try:
            body = await get_json(
                f"{c.BASE_URL}{c.WORKS}", params=params, headers=_user_agent(s.mailto)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.WorksResponse.model_validate(body)
        note = _list_note(result.message)
        items = [c.Work.model_validate(it) for it in result.message.items]
        if not items:
            return f"검색 결과 없음. ({note})"
        return note + "\n" + "\n".join(_work_line(w) for w in items)

    @mcp.tool
    async def crossref_get_work(doi: str) -> str:
        """단일 work를 DOI로 조회한다(GET /works/{doi}).

        Args:
            doi: Crossref DOI(예: `10.5555/12345678`). 없는 DOI는 404로 매핑된다.
        """
        s = CrossrefSettings()
        params = c.build_params(mailto=s.mailto)
        try:
            body = await get_json(
                f"{c.BASE_URL}{c.work_path(doi)}", params=params, headers=_user_agent(s.mailto)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        w = c.WorkResponse.model_validate(body).message
        lines = [
            f"[{w.doi or '?'}] ({_year(w.published)}) {_title(w.title)}",
            f"- 타입: {w.type or '?'} · 인용 "
            f"{w.is_referenced_by_count if w.is_referenced_by_count is not None else '?'}회",
            f"- 저자: {_authors(w.author)}",
        ]
        container = w.container_title[0] if w.container_title else None
        if container:
            lines.append(f"- 수록: {container}")
        if w.publisher:
            lines.append(f"- 발행처: {w.publisher}")
        return "\n".join(lines)

    @mcp.tool
    async def crossref_search_journals(
        query: str | None = None,
        rows: int = c.DEFAULT_ROWS,
        offset: int = 0,
    ) -> str:
        """Crossref에서 저널(journals)을 검색/나열한다(GET /journals).

        Args:
            query: 저널 제목/발행처 검색어. 미지정 시 나열한다.
            rows: 페이지 크기. 기본 20, 0..1000.
            offset: 시작 오프셋(0부터). 0..10000.
        """
        s = CrossrefSettings()
        try:
            params = c.build_params(query=query, rows=rows, offset=offset, mailto=s.mailto)
        except ValueError as e:
            return str(e)

        try:
            body = await get_json(
                f"{c.BASE_URL}{c.JOURNALS}", params=params, headers=_user_agent(s.mailto)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.JournalsResponse.model_validate(body)
        note = _list_note(result.message)
        items = [c.Journal.model_validate(it) for it in result.message.items]
        if not items:
            return f"검색 결과 없음. ({note})"
        lines = [note]
        for j in items:
            issn = ", ".join(j.issn) if j.issn else "?"
            lines.append(f"- {j.title or '(제목 없음)'} — {j.publisher or '?'} · ISSN {issn}")
        return "\n".join(lines)

    @mcp.tool
    async def crossref_get_journal(issn: str) -> str:
        """단일 journal을 ISSN으로 조회한다(GET /journals/{issn}).

        Args:
            issn: 저널 ISSN(예: `2167-8359`). 없는 ISSN은 404로 매핑된다.
        """
        s = CrossrefSettings()
        params = c.build_params(mailto=s.mailto)
        try:
            body = await get_json(
                f"{c.BASE_URL}{c.journal_path(issn)}", params=params, headers=_user_agent(s.mailto)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        j = c.JournalResponse.model_validate(body).message
        issns = ", ".join(j.issn) if j.issn else "?"
        lines = [
            f"{j.title or '(제목 없음)'}",
            f"- 발행처: {j.publisher or '?'}",
            f"- ISSN: {issns}",
        ]
        total_dois = (j.counts or {}).get("total-dois")
        if total_dois is not None:
            lines.append(f"- 등록 DOI: {total_dois}건")
        return "\n".join(lines)
