"""Notion 워크스페이스 읽기 MCP 도구 + 런타임 배선(자격증명·요청 조립·에러 매핑).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 읽기다.

인증은 **필수** Bearer 토큰(`NOTION_TOKEN`) — 사전발급 토큰(Internal Integration Token 또는 PAT)
이라 인터랙티브 OAuth가 아니다 → make_auth_client 없음(zotero/openalex/line과 동형). 토큰이
없으면 HTTP 호출 전에 안내 문자열을 반환한다.

database 읽기 흐름(2025-09-03+): `notion_get_database`(→data_sources) →
`notion_get_data_source`(→properties) → `notion_query_data_source`(→행).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json, post_json
from arcsolve.services.notion import contract as n

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class NotionSettings(BaseSettings):
    """NOTION_* 환경변수에서 자격증명을 로드한다.

    - token: Bearer 토큰(필수). Internal Integration Token 또는 Personal Access Token(PAT).
    """

    model_config = SettingsConfigDict(env_prefix="NOTION_", env_file=".env", extra="ignore")
    token: str | None = None


_MISSING_TOKEN = (
    "설정 오류: NOTION_TOKEN이 없습니다. Notion 통합(integration)의 Internal Integration Token "
    "또는 PAT를 발급해 NOTION_TOKEN에 설정하세요. "
    "(발급: https://www.notion.so/my-integrations · 읽을 페이지/DB를 통합과 공유해야 합니다.)"
)


def _explain(e: UpstreamError) -> str:
    """문서화된 상태코드를 사람이 읽을 메시지로 매핑한다.

    Notion 에러 봉투는 `{object:"error", status, code, message}`. message/code를 노출한다
    (dict가 아니면 원문 오염 방지로 detail을 비운다).
    출처(상태코드): https://developers.notion.com/reference/status-codes
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = payload.get("message") if payload else None
    code = payload.get("code") if payload else None
    detail = f" {msg}" if msg else ""  # 비-JSON 본문은 노출하지 않음
    suffix = f" [{code}]" if code else ""
    if e.status == 400:
        return f"요청 오류(400): 본문/필터/page_size를 확인하세요.{detail}{suffix}"
    if e.status == 401:
        return f"인증 오류(401): NOTION_TOKEN이 무효이거나 만료되었습니다.{detail}{suffix}"
    if e.status == 403:
        return (
            "권한 오류(403): 이 통합에 해당 작업 권한이 없습니다(읽기 권한/콘텐츠 capability 확인)."
            f"{detail}{suffix}"
        )
    if e.status == 404:
        return (
            "찾을 수 없음(404): id가 틀렸거나, 해당 페이지/DB를 통합과 **공유하지 않았을** 수 "
            f"있습니다(Notion에서 '연결' 추가 필요).{detail}{suffix}"
        )
    if e.status == 429:
        return f"요청 한도 초과(429): 잠시 후 재시도하세요.{detail}{suffix}"
    return f"Notion API 오류 {e.status}:{detail}{suffix}"


def _list_note(result: n.ListResponse) -> str:
    """list 응답으로 페이지네이션 안내 문자열을 만든다."""
    if result.has_more and result.next_cursor:
        return f"(다음 페이지 있음 · start_cursor={result.next_cursor})"
    return "(마지막 페이지)"


def _search_line(item: dict) -> str:
    """search 결과 1줄: `- [object] id — 제목`. object에 따라 제목 추출이 다르다."""
    obj = item.get("object") or "?"
    oid = item.get("id") or "?"
    if obj == "page":
        title = n.page_title(item.get("properties"))
    else:  # data_source / database 등은 최상위 title rich_text 배열
        title = n.rich_text_to_plain(item.get("title")) or "(제목 없음)"
    return f"- [{obj}] {oid} — {title}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def notion_search(
        query: str | None = None,
        filter_type: str | None = None,
        page_size: int = n.DEFAULT_PAGE_SIZE,
        start_cursor: str | None = None,
    ) -> str:
        """Notion 워크스페이스에서 page/data source를 제목으로 검색한다(POST /search).

        통합과 공유된 콘텐츠만 검색된다.

        Args:
            query: 제목 전문 검색어. 미지정 시 접근 가능한 항목을 나열한다.
            filter_type: 결과 종류 한정 — "page" 또는 "data_source"(미지정=둘 다).
            page_size: 페이지 크기. 기본 25, 1..100.
            start_cursor: 다음 페이지 커서(이전 응답의 next_cursor).
        """
        s = NotionSettings()
        if not s.token:
            return _MISSING_TOKEN
        try:
            body = n.build_search_body(
                query=query, filter_type=filter_type, page_size=page_size, start_cursor=start_cursor
            )
        except ValueError as e:  # page_size 범위·filter_type 등 계약 위반은 HTTP 전에 막힘
            return str(e)

        try:
            data = await post_json(
                f"{n.BASE_URL}{n.SEARCH}", headers=n.headers(s.token), json=body
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(data, dict):
            return f"응답: {data}"
        result = n.ListResponse.model_validate(data)
        if not result.results:
            return "검색 결과 없음."
        lines = [_search_line(it) for it in result.results]
        return "\n".join(lines) + "\n" + _list_note(result)

    @mcp.tool
    async def notion_get_page(page_id: str) -> str:
        """단일 페이지의 메타데이터를 조회한다(GET /pages/{id}).

        본문 블록은 `notion_get_block_children(page_id)`로 따로 읽는다.

        Args:
            page_id: 페이지 ID(UUID).
        """
        s = NotionSettings()
        if not s.token:
            return _MISSING_TOKEN
        try:
            data = await get_json(
                f"{n.BASE_URL}{n.page_path(page_id)}", headers=n.headers(s.token)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(data, dict):
            return f"응답: {data}"
        page = n.Page.model_validate(data)
        lines = [
            f"[page] {page.id} — {n.page_title(page.properties)}",
            f"- 수정: {page.last_edited_time or '?'} · 휴지통: {'예' if page.in_trash else '아니오'}",
        ]
        if page.url:
            lines.append(f"- URL: {page.url}")
        return "\n".join(lines)

    @mcp.tool
    async def notion_get_block_children(
        block_id: str,
        page_size: int = n.DEFAULT_PAGE_SIZE,
        start_cursor: str | None = None,
    ) -> str:
        """블록(또는 페이지)의 자식 블록을 나열해 본문을 읽는다(GET /blocks/{id}/children).

        페이지 본문을 읽으려면 block_id에 page_id를 넣는다.

        Args:
            block_id: 블록 ID 또는 페이지 ID(UUID).
            page_size: 페이지 크기. 기본 25, 1..100.
            start_cursor: 다음 페이지 커서.
        """
        s = NotionSettings()
        if not s.token:
            return _MISSING_TOKEN
        try:
            params = n.page_params(page_size=page_size, start_cursor=start_cursor)
        except ValueError as e:
            return str(e)

        try:
            data = await get_json(
                f"{n.BASE_URL}{n.blocks_children_path(block_id)}",
                headers=n.headers(s.token),
                params=params,
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(data, dict):
            return f"응답: {data}"
        result = n.ListResponse.model_validate(data)
        if not result.results:
            return "자식 블록 없음."
        lines = []
        for b in result.results:
            btype = b.get("type") or "?"
            text = n.block_plain_text(b)
            child = " ⤵" if b.get("has_children") else ""
            lines.append(f"- [{btype}]{child} {text}".rstrip())
        return "\n".join(lines) + "\n" + _list_note(result)

    @mcp.tool
    async def notion_get_database(database_id: str) -> str:
        """database를 조회해 자식 data source 목록을 얻는다(GET /databases/{id}).

        2025-09-03+에서 database는 data source 컨테이너다. 행을 쿼리하려면 여기서 얻은
        data source id로 `notion_query_data_source`를 호출한다.

        Args:
            database_id: 데이터베이스 ID(UUID).
        """
        s = NotionSettings()
        if not s.token:
            return _MISSING_TOKEN
        try:
            data = await get_json(
                f"{n.BASE_URL}{n.database_path(database_id)}", headers=n.headers(s.token)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(data, dict):
            return f"응답: {data}"
        db = n.Database.model_validate(data)
        title = n.rich_text_to_plain(db.title) or "(제목 없음)"
        lines = [f"[database] {db.id} — {title}", f"- data source {len(db.data_sources)}개:"]
        for ds in db.data_sources:
            lines.append(f"  - {ds.get('id', '?')} — {ds.get('name') or '(이름 없음)'}")
        return "\n".join(lines)

    @mcp.tool
    async def notion_get_data_source(data_source_id: str) -> str:
        """data source의 스키마(프로퍼티)를 조회한다(GET /data_sources/{id}).

        쿼리에 쓸 수 있는 프로퍼티 이름·타입을 확인한다.

        Args:
            data_source_id: 데이터 소스 ID(UUID; `notion_get_database`로 얻음).
        """
        s = NotionSettings()
        if not s.token:
            return _MISSING_TOKEN
        try:
            data = await get_json(
                f"{n.BASE_URL}{n.data_source_path(data_source_id)}", headers=n.headers(s.token)
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(data, dict):
            return f"응답: {data}"
        ds = n.DataSource.model_validate(data)
        title = n.rich_text_to_plain(ds.title) or "(제목 없음)"
        lines = [f"[data_source] {ds.id} — {title}", f"- 프로퍼티 {len(ds.properties)}개:"]
        for name, spec in ds.properties.items():
            ptype = spec.get("type") if isinstance(spec, dict) else "?"
            lines.append(f"  - {name}: {ptype}")
        return "\n".join(lines)

    @mcp.tool
    async def notion_query_data_source(
        data_source_id: str,
        filter: dict | None = None,  # noqa: A002 (공식 본문 키 "filter")
        sorts: list | None = None,
        page_size: int = n.DEFAULT_PAGE_SIZE,
        start_cursor: str | None = None,
    ) -> str:
        """data source의 행(page)을 쿼리한다(POST /data_sources/{id}/query).

        Args:
            data_source_id: 데이터 소스 ID(UUID).
            filter: Notion 필터 객체(그대로 전달). 예: {"property":"Status","status":{"equals":"Done"}}.
            sorts: Notion 정렬 배열(그대로 전달). 예: [{"property":"Name","direction":"ascending"}].
            page_size: 페이지 크기. 기본 25, 1..100.
            start_cursor: 다음 페이지 커서.
        """
        s = NotionSettings()
        if not s.token:
            return _MISSING_TOKEN
        try:
            body = n.build_query_body(
                filter=filter, sorts=sorts, page_size=page_size, start_cursor=start_cursor
            )
        except ValueError as e:
            return str(e)

        try:
            data = await post_json(
                f"{n.BASE_URL}{n.data_source_query_path(data_source_id)}",
                headers=n.headers(s.token),
                json=body,
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(data, dict):
            return f"응답: {data}"
        result = n.ListResponse.model_validate(data)
        if not result.results:
            return "행 없음."
        lines = []
        for row in result.results:
            oid = row.get("id") or "?"
            lines.append(f"- {oid} — {n.page_title(row.get('properties'))}")
        return "\n".join(lines) + "\n" + _list_note(result)
