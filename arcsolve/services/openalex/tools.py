"""OpenAlex 학술 그래프 읽기 MCP 도구 + 런타임 배선(자격증명·요청 조립·에러 매핑).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **선택**(키 없이도 동작). 키(`api_key`)·polite 이메일(`mailto`)은 헤더가 아니라
**쿼리 파라미터**다 → contract.build_params가 params에 넣는다. 페이지네이션/건수는 응답
**본문 meta**에 실리므로 코어 `get_json`만 쓴다(헤더 동사 불필요). 인터랙티브 OAuth가 아니므로
make_auth_client 없음(zotero/line과 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.openalex import contract as o

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class OpenAlexSettings(BaseSettings):
    """OPENALEX_* 환경변수에서 (선택) 자격증명을 로드한다.

    - api_key: API 키(선택, 권장). 있으면 쿼리 `api_key=`로 보낸다.
    - mailto: polite pool 이메일(선택). 있으면 쿼리 `mailto=`로 보낸다.
    둘 다 없어도 동작한다(무료 일일 크레딧).
    """

    model_config = SettingsConfigDict(env_prefix="OPENALEX_", env_file=".env", extra="ignore")
    api_key: str | None = None
    mailto: str | None = None


def _explain(e: UpstreamError) -> str:
    """문서화된 상태코드를 사람이 읽을 메시지로 매핑한다.

    OpenAlex 에러 봉투는 JSON일 때 `{error, message}` — message만 노출한다(404 등은 본문이
    HTML일 수 있어, dict가 아니면 detail을 비워 원문 오염을 막는다).
    출처(상태코드): https://developers.openalex.org/guides/authentication
          + https://developers.openalex.org/how-to-use-the-api/get-lists-of-entities
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = payload.get("message") if payload else None
    detail = f" {msg}" if msg else ""  # 비-JSON(HTML) 본문은 노출하지 않음
    if e.status == 400:
        # 잘못된 쿼리/필터/per-page 범위 등 — message에 사유가 담긴다.
        return f"요청 오류(400): 쿼리/필터/per-page를 확인하세요.{detail}"
    if e.status == 401:
        # 라이브 확인: 무효/누락 키는 401 {"error":"Invalid or missing API key"}.
        return (
            "인증 오류(401): API 키가 무효이거나 누락되었습니다. OPENALEX_API_KEY를 확인하세요"
            f"(키 없이도 무료 크레딧으로 동작).{detail}"
        )
    if e.status == 403:
        return f"권한/크레딧 오류(403): 일일 크레딧 초과 또는 접근 권한 문제일 수 있습니다.{detail}"
    if e.status == 404:
        return "찾을 수 없음(404): work/author id(OpenAlex ID·DOI·ORCID)를 확인하세요."
    if e.status == 429:
        return (
            "요청 한도 초과(429): 잠시 후 재시도하세요. "
            f"OPENALEX_MAILTO로 polite pool을 쓰면 안정적입니다.{detail}"
        )
    return f"OpenAlex API 오류 {e.status}:{detail or ' ' + str(e.payload)}"


def _author_summary(authorships: list[dict] | None) -> str:
    """authorships에서 '첫 저자 외 N명' 형태의 짧은 요약을 만든다."""
    if not authorships:
        return "(저자 없음)"
    first = authorships[0].get("author") or {}
    name = first.get("display_name") or "(이름 없음)"
    extra = len(authorships) - 1
    return f"{name} 외 {extra}명" if extra > 0 else name


def _work_line(w: o.Work) -> str:
    """검색 결과 1줄: `- [id] (year) display_name — 첫 저자 외`."""
    title = w.display_name or w.title or "(제목 없음)"
    year = w.publication_year if w.publication_year is not None else "?"
    return f"- [{w.id}] ({year}) {title} — {_author_summary(w.authorships)}"


def _list_note(meta: o.Meta) -> str:
    """리스트 응답 meta로 '총 N건 · page P' 안내 문자열을 만든다."""
    note = f"총 {meta.count}건"
    if meta.page is not None:
        note += f" · page {meta.page}"
    return note


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def openalex_search_works(
        query: str | None = None,
        filter: str | None = None,  # noqa: A002 (공식 파라미터명 "filter")
        sort: str | None = None,
        per_page: int = o.DEFAULT_PER_PAGE,
        page: int = 1,
    ) -> str:
        """OpenAlex에서 학술 논문(works)을 검색/나열한다(GET /works).

        Args:
            query: 전문 검색어(search). 미지정 시 필터/정렬만으로 나열한다.
            filter: 필터식 `attr:value`(콤마=AND, `|`=OR, `!`=NOT).
                예: `publication_year:2020`, `is_oa:true`.
            sort: 정렬(예: `cited_by_count:desc`).
            per_page: 페이지 크기. 기본 25, 1..200.
            page: 페이지 번호(1부터). page 기반은 최대 10,000건까지.
        """
        s = OpenAlexSettings()
        try:
            params = o.build_params(
                query=query, filter=filter, sort=sort, per_page=per_page, page=page,
                api_key=s.api_key, mailto=s.mailto,
            )
        except ValueError as e:  # per_page 범위 등 계약 위반은 HTTP 전에 막힌다
            return str(e)

        try:
            body = await get_json(f"{o.BASE_URL}{o.WORKS}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = o.WorksList.model_validate(body)
        note = _list_note(result.meta)
        if not result.results:
            return f"검색 결과 없음. ({note})"
        return note + "\n" + "\n".join(_work_line(w) for w in result.results)

    @mcp.tool
    async def openalex_get_work(work_id: str) -> str:
        """단일 work를 조회한다(GET /works/{id}).

        Args:
            work_id: OpenAlex ID(`W…`), DOI(`10.7717/peerj.4375`·`doi:…`·`https://doi.org/…`).
                bare DOI는 자동으로 `doi:`로 정규화된다.
        """
        s = OpenAlexSettings()
        params = o.build_params(api_key=s.api_key, mailto=s.mailto)
        try:
            body = await get_json(f"{o.BASE_URL}{o.work_path(work_id)}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        w = o.Work.model_validate(body)
        title = w.display_name or w.title or "(제목 없음)"
        year = w.publication_year if w.publication_year is not None else "?"
        lines = [
            f"[{w.id}] ({year}) {title}",
            f"- 타입: {w.type or '?'} · 인용 {w.cited_by_count if w.cited_by_count is not None else '?'}회",
            f"- 저자: {_author_summary(w.authorships)}",
        ]
        if w.doi:
            lines.append(f"- DOI: {w.doi}")
        return "\n".join(lines)

    @mcp.tool
    async def openalex_search_authors(
        query: str | None = None,
        per_page: int = o.DEFAULT_PER_PAGE,
        page: int = 1,
    ) -> str:
        """OpenAlex에서 저자(authors)를 검색/나열한다(GET /authors).

        Args:
            query: 전문 검색어(search). 미지정 시 나열한다.
            per_page: 페이지 크기. 기본 25, 1..200.
            page: 페이지 번호(1부터).
        """
        s = OpenAlexSettings()
        try:
            params = o.build_params(
                query=query, per_page=per_page, page=page,
                api_key=s.api_key, mailto=s.mailto,
            )
        except ValueError as e:
            return str(e)

        try:
            body = await get_json(f"{o.BASE_URL}{o.AUTHORS}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = o.AuthorsList.model_validate(body)
        note = _list_note(result.meta)
        if not result.results:
            return f"검색 결과 없음. ({note})"
        lines = [note]
        for a in result.results:
            name = a.display_name or "(이름 없음)"
            works = a.works_count if a.works_count is not None else "?"
            cites = a.cited_by_count if a.cited_by_count is not None else "?"
            lines.append(f"- [{a.id}] {name} — 논문 {works}편 · 인용 {cites}회")
        return "\n".join(lines)

    @mcp.tool
    async def openalex_get_author(author_id: str) -> str:
        """단일 author를 조회한다(GET /authors/{id}).

        Args:
            author_id: OpenAlex ID(`A…`) 또는 ORCID(`0000-0002-...`·`orcid:…`·URL).
                bare ORCID는 자동으로 `orcid:`로 정규화된다.
        """
        s = OpenAlexSettings()
        params = o.build_params(api_key=s.api_key, mailto=s.mailto)
        try:
            body = await get_json(f"{o.BASE_URL}{o.author_path(author_id)}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        a = o.Author.model_validate(body)
        name = a.display_name or "(이름 없음)"
        works = a.works_count if a.works_count is not None else "?"
        cites = a.cited_by_count if a.cited_by_count is not None else "?"
        lines = [f"[{a.id}] {name}", f"- 논문 {works}편 · 인용 {cites}회"]
        if a.orcid:
            lines.append(f"- ORCID: {a.orcid}")
        return "\n".join(lines)
