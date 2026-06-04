"""Semantic Scholar Academic Graph API 학술 그래프 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **선택**(키 없이 공유 풀로 동작). 키는 `x-api-key` **헤더**다(OpenAlex의 쿼리 파라미터와
달리 헤더 — env `SEMANTICSCHOLAR_API_KEY`). 반환 필드는 `fields` 파라미터로 선택하고, 페이지네이션/
건수는 응답 **본문**(total/offset/next)에 실리므로 코어 `get_json`만 쓴다(헤더 동사 불필요).
인터랙티브 OAuth가 아니므로 make_auth_client 없음(openalex/crossref와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.semanticscholar import contract as s

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class SemanticScholarSettings(BaseSettings):
    """SEMANTICSCHOLAR_* 환경변수에서 (선택) API 키를 로드한다.

    - api_key: API 키(선택). 있으면 `x-api-key` 헤더로 보낸다(1 RPS 전용 풀).
    없으면 공유 풀(무인증)로 동작한다 — 트래픽 많을 때 429가 잦을 수 있다.
    """

    model_config = SettingsConfigDict(
        env_prefix="SEMANTICSCHOLAR_", env_file=".env", extra="ignore"
    )
    api_key: str | None = None


def _headers(api_key: str | None) -> dict[str, str] | None:
    """키가 있으면 `x-api-key` 인증 헤더를 만든다(없으면 None — 공유 풀).

    출처: 튜토리얼 ({"x-api-key": api_key}) — 헤더 인증(쿼리 파라미터 아님).
    """
    return {"x-api-key": api_key} if api_key else None


def _explain(e: UpstreamError) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    S2 에러 봉투는 JSON: 검증 실패/404는 `{"error": "..."}`, 레이트리밋은
    `{"message": "...", "code": "429"}`. error 또는 message 텍스트만 노출한다(둘 다 없으면 비움).
    출처: 라이브(/paper/search offset 위반 400, /paper/<bad> 404, 429 too-many-requests)
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        msg = payload.get("error") or payload.get("message")
    detail = f" {msg.strip()}" if msg else ""  # 비-JSON 본문은 노출하지 않음
    if e.status == 400:
        return f"요청 오류(400): query/fields/limit/offset/year를 확인하세요.{detail}"
    if e.status == 403:
        return f"인증 오류(403): API 키가 무효일 수 있습니다. SEMANTICSCHOLAR_API_KEY를 확인하세요.{detail}"
    if e.status == 404:
        return f"찾을 수 없음(404): paper/author id를 확인하세요(접두 규칙: DOI:·ARXIV: 등).{detail}"
    if e.status == 429:
        return (
            "요청 한도 초과(429): 공유 풀이 혼잡합니다. 잠시 후 재시도하세요. "
            f"SEMANTICSCHOLAR_API_KEY를 쓰면 전용 풀(1 RPS)로 안정적입니다.{detail}"
        )
    return f"Semantic Scholar API 오류 {e.status}:{detail}"


def _author_summary(authors: list[dict] | None) -> str:
    """authors 배열에서 '첫 저자 외 N명' 형태의 짧은 요약을 만든다.

    authors는 `fields`에 포함될 때만 온다(없으면 '(저자 정보 없음)').
    """
    if not authors:
        return "(저자 정보 없음)"
    name = authors[0].get("name") or "(이름 없음)"
    extra = len(authors) - 1
    return f"{name} 외 {extra}명" if extra > 0 else name


def _paper_line(p: s.Paper) -> str:
    """검색 결과 1줄: `- [paperId] (year) title — 첫 저자 외`."""
    pid = p.paperId or "?"
    year = p.year if p.year is not None else "?"
    return f"- [{pid}] ({year}) {p.title or '(제목 없음)'} — {_author_summary(p.authors)}"


def _list_note(total: int | None, offset: int | None, next_: int | None) -> str:
    """검색 응답 봉투로 '총 N건 · offset M' 안내 문자열을 만든다(next 있으면 표시)."""
    note = f"총 {total if total is not None else '?'}건"
    if offset is not None:
        note += f" · offset {offset}"
    if next_ is not None:
        note += f" · 다음 offset {next_}"
    return note


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def s2_search_papers(
        query: str,
        fields: str | None = None,
        limit: int = s.DEFAULT_LIMIT,
        offset: int = 0,
        year: str | None = None,
    ) -> str:
        """Semantic Scholar에서 논문(papers)을 relevance 검색한다(GET /paper/search).

        Args:
            query: 자유 전문 검색어(특수 구문 없음). 필수.
            fields: 반환 필드(콤마 구분). 미지정 시 상류 기본 `paperId,title`.
                예: `title,year,authors.name,externalIds,citationCount,venue`.
            limit: 페이지 크기. 기본 10, 1..100. offset+limit은 1000 미만이어야 한다.
            offset: 시작 오프셋(0부터). offset+limit < 1000(이상은 bulk 필요 — 범위 밖).
            year: 출판 연도 필터(예: `2015`·`2010-2020`·`2015-`·`-2015`).
        """
        s_ = SemanticScholarSettings()
        try:
            s.validate_limit(limit, maximum=s.MAX_PAPER_LIMIT)
            s.validate_relevance_window(offset, limit)
        except ValueError as e:  # limit/offset 범위 위반은 HTTP 전에 막힌다
            return str(e)
        params = s.build_params(
            query=query, fields=fields, limit=limit, offset=offset, year=year
        )

        try:
            body = await get_json(
                f"{s.BASE_URL}{s.PAPER_SEARCH}", params=params, headers=_headers(s_.api_key)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = s.PaperSearchResponse.model_validate(body)
        note = _list_note(result.total, result.offset, result.next)
        if not result.data:
            return f"검색 결과 없음. ({note})"
        return note + "\n" + "\n".join(_paper_line(p) for p in result.data)

    @mcp.tool
    async def s2_get_paper(id: str, fields: str | None = None) -> str:  # noqa: A002
        """단일 paper를 조회한다(GET /paper/{id}).

        Args:
            id: S2 paperId(SHA 해시) 또는 외부 ID(접두 필수):
                `DOI:10.../...`·`ARXIV:1801.00862`·`CorpusId:44098998`·`MAG:`·`ACL:`·`PMID:`·`PMCID:`·`URL:`.
            fields: 반환 필드(콤마 구분). 미지정 시 상류 기본 `paperId,title`.
        """
        s_ = SemanticScholarSettings()
        params = s.build_params(fields=fields)
        try:
            body = await get_json(
                f"{s.BASE_URL}{s.paper_path(id)}", params=params, headers=_headers(s_.api_key)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        p = s.Paper.model_validate(body)
        year = p.year if p.year is not None else "?"
        lines = [
            f"[{p.paperId or '?'}] ({year}) {p.title or '(제목 없음)'}",
            f"- 저자: {_author_summary(p.authors)}",
        ]
        if p.citationCount is not None:
            lines.append(f"- 인용 {p.citationCount}회")
        if p.venue:
            lines.append(f"- 수록: {p.venue}")
        doi = (p.externalIds or {}).get("DOI")
        if doi:
            lines.append(f"- DOI: {doi}")
        return "\n".join(lines)

    @mcp.tool
    async def s2_search_authors(
        query: str,
        fields: str | None = None,
        limit: int = s.DEFAULT_LIMIT,
        offset: int = 0,
    ) -> str:
        """Semantic Scholar에서 저자(authors)를 검색한다(GET /author/search).

        Args:
            query: 자유 전문 검색어. 필수.
            fields: 반환 필드(콤마 구분). 미지정 시 상류 기본 `authorId,name`.
                예: `name,paperCount,citationCount,hIndex,url`.
            limit: 페이지 크기. 기본 10, 1..1000.
            offset: 시작 오프셋(0부터).
        """
        s_ = SemanticScholarSettings()
        try:
            s.validate_limit(limit, maximum=s.MAX_AUTHOR_LIMIT)
        except ValueError as e:
            return str(e)
        params = s.build_params(query=query, fields=fields, limit=limit, offset=offset)

        try:
            body = await get_json(
                f"{s.BASE_URL}{s.AUTHOR_SEARCH}", params=params, headers=_headers(s_.api_key)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = s.AuthorSearchResponse.model_validate(body)
        note = _list_note(result.total, result.offset, result.next)
        if not result.data:
            return f"검색 결과 없음. ({note})"
        lines = [note]
        for a in result.data:
            name = a.name or "(이름 없음)"
            papers = a.paperCount if a.paperCount is not None else "?"
            cites = a.citationCount if a.citationCount is not None else "?"
            lines.append(f"- [{a.authorId or '?'}] {name} — 논문 {papers}편 · 인용 {cites}회")
        return "\n".join(lines)

    @mcp.tool
    async def s2_get_author(id: str, fields: str | None = None) -> str:  # noqa: A002
        """단일 author를 조회한다(GET /author/{id}).

        Args:
            id: S2 authorId(숫자 문자열, 예: `7284134`).
            fields: 반환 필드(콤마 구분). 미지정 시 상류 기본 `authorId,name`.
                예: `name,paperCount,citationCount,hIndex,url`.
        """
        s_ = SemanticScholarSettings()
        params = s.build_params(fields=fields)
        try:
            body = await get_json(
                f"{s.BASE_URL}{s.author_path(id)}", params=params, headers=_headers(s_.api_key)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        a = s.Author.model_validate(body)
        name = a.name or "(이름 없음)"
        papers = a.paperCount if a.paperCount is not None else "?"
        cites = a.citationCount if a.citationCount is not None else "?"
        lines = [f"[{a.authorId or '?'}] {name}", f"- 논문 {papers}편 · 인용 {cites}회"]
        if a.hIndex is not None:
            lines.append(f"- h-index: {a.hIndex}")
        if a.url:
            lines.append(f"- URL: {a.url}")
        return "\n".join(lines)
