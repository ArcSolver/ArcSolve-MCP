"""Zotero 라이브러리 읽기 MCP 도구 + 런타임 배선(백엔드 해석·자격증명).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

한 서비스 = 두 백엔드(web / local). ZoteroSettings._resolve()가 (base, prefix, headers,
source)를 만들어 분기한다. 인증은 사전발급 API 키(헤더) — 인터랙티브 OAuth 아님
(line과 동형) → make_auth_client 없음. 로컬 백엔드는 읽기 전용.

페이지네이션/버전/백오프가 응답 **헤더**에 실리므로 list/search 계열은 코어의
`get_with_headers` + `parse_link_header`를 쓰고, 단건 조회는 `get_json`을 쓴다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import (
    UpstreamError,
    get_json,
    get_with_headers,
    parse_link_header,
)
from arcsolve.services.zotero import contract as z

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class ZoteroSettings(BaseSettings):
    """ZOTERO_* 환경변수에서 백엔드 설정/자격증명을 로드한다.

    - source: web | local (미지정=auto: api_key 있으면 web, 없으면 local)
    - api_key: web 인증(공개 라이브러리면 생략 가능)
    - user_id / group_id: web 라이브러리 식별(group 지정 시 group 우선)
    - local_base: 로컬 데스크톱 API base(기본 http://localhost:23119/api)
    """

    model_config = SettingsConfigDict(env_prefix="ZOTERO_", env_file=".env", extra="ignore")
    source: str | None = None  # "web" | "local" | None(auto)
    api_key: str | None = None
    user_id: str | None = None
    group_id: str | None = None
    local_base: str = z.DEFAULT_LOCAL_BASE

    def resolved_source(self) -> str:
        """source를 web/local로 확정한다(auto면 api_key 유무로 결정)."""
        if self.source:
            return self.source.strip().lower()
        return "web" if self.api_key else "local"


class BackendError(ValueError):
    """백엔드 설정이 미흡/모순일 때 — 사람이 읽을 안내 문자열을 담는다."""


def _resolve(s: ZoteroSettings) -> tuple[str, str, dict[str, str], str]:
    """(base, prefix, headers, source)로 백엔드를 해석한다. 문제가 있으면 BackendError.

    - web: base=https://api.zotero.org · prefix=users/<id> 또는 groups/<id> ·
      headers={Zotero-API-Version:3, (Zotero-API-Key:<key> if key)}
    - local: base=<local_base> · prefix=users/0 · headers={Zotero-API-Version:3}(무인증)
    출처: https://www.zotero.org/support/dev/web_api/v3/basics
          + server_localAPI.js(로컬 base/users0/무인증)
    """
    source = s.resolved_source()
    if source == "local":
        # 로컬은 무인증·읽기전용·users/0 고정.
        return (
            s.local_base.rstrip("/"),
            z.user_prefix(z.LOCAL_USER_ID),
            z.base_headers(None),
            "local",
        )
    if source == "web":
        if s.group_id:
            prefix = z.group_prefix(s.group_id)
        elif s.user_id:
            prefix = z.user_prefix(s.user_id)
        else:
            raise BackendError(
                "설정 오류(web): ZOTERO_USER_ID 또는 ZOTERO_GROUP_ID 중 하나가 필요합니다. "
                "(로컬 데스크톱 API를 쓰려면 ZOTERO_SOURCE=local 로 두세요.)"
            )
        # 공개 라이브러리면 api_key 없이도 동작하므로 키 없음을 막지 않는다(헤더에서 생략).
        return (z.WEB_BASE_URL, prefix, z.base_headers(s.api_key), "web")
    raise BackendError(
        f"설정 오류: ZOTERO_SOURCE는 'web' 또는 'local'이어야 합니다(현재 {source!r})."
    )


def _explain(e: UpstreamError, source: str) -> str:
    """문서화된 상태코드를 사람이 읽을 메시지로 매핑한다.

    출처(상태코드/헤더): https://www.zotero.org/support/dev/web_api/v3/basics
          + server_localAPI.js(local 403 = httpServer.localAPI.enabled 비활성)
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    detail = (payload.get("message") if payload else None) or e.payload
    if e.status == 400:
        if source == "local":
            return (
                "요청 오류(400): 로컬 API는 로그인 사용자(users/0)만 제공합니다. "
                f"다른 userID/groupID는 쓸 수 없습니다. {detail}"
            )
        return f"요청 오류(400): 쿼리/식별자를 확인하세요. {detail}"
    if e.status == 403:
        if source == "local":
            return (
                "권한 없음(403): 로컬 API가 비활성일 수 있습니다. Zotero 데스크톱에서 "
                "설정 > 고급 > 'Allow other applications ... local API'(pref "
                "httpServer.localAPI.enabled)를 켜세요."
            )
        return (
            "권한 없음(403): API 키가 무효이거나 이 라이브러리 접근 권한이 없습니다. "
            f"ZOTERO_API_KEY/권한을 확인하세요. {detail}"
        )
    if e.status == 404:
        return f"찾을 수 없음(404): 아이템/컬렉션 키 또는 라이브러리 경로를 확인하세요. {detail}"
    if e.status in (429, 503):
        # UpstreamError는 본문만 전달하므로(코어) Backoff/Retry-After 초 수는 여기서 알 수 없다.
        # 성공 응답에 실린 백오프는 list 도구의 _pagination_note가 별도로 노출한다.
        # 출처: https://www.zotero.org/support/dev/web_api/v3/basics (Backoff/Retry-After)
        return f"요청 한도/과부하({e.status}). 잠시 후 재시도하세요. {detail}"
    return f"Zotero API 오류 {e.status}: {detail}"


def _explain_connect(s: ZoteroSettings, source: str, base: str) -> str:
    """연결 거부(local 앱 미실행/포트 상이)를 사람이 읽을 메시지로.

    httpx.ConnectError는 UpstreamError가 아니므로 도구에서 직접 잡아 이 메시지를 쓴다.
    """
    if source == "local":
        return (
            f"연결 실패: 로컬 Zotero API({base})에 연결할 수 없습니다. "
            "Zotero 데스크톱이 실행 중인지, 로컬 API가 켜져 있는지, 포트(기본 23119)가 "
            "맞는지 확인하세요(ZOTERO_LOCAL_BASE로 변경 가능)."
        )
    return f"연결 실패: {base} 에 연결할 수 없습니다. 네트워크/주소를 확인하세요."


def _pagination_note(headers: dict[str, str], start: int, count: int) -> str:
    """응답 헤더(Total-Results / Link rel=next)로 페이지네이션 안내 문자열을 만든다.

    출처: https://www.zotero.org/support/dev/web_api/v3/basics
    """
    total = headers.get(z.HDR_TOTAL_RESULTS)
    links = parse_link_header(headers.get(z.HDR_LINK))
    next_start = z.start_from_next_link(links.get("next"))
    shown_to = start + count
    if total is not None:
        note = f"총 {total}건 중 {start + 1}-{shown_to}건"
    else:
        note = f"{start + 1}-{shown_to}건"
    if next_start is not None:
        note += f" · 다음 start={next_start}"
    # 과부하 신호가 성공 응답에 실렸으면 함께 알린다.
    backoff = headers.get(z.HDR_BACKOFF) or headers.get(z.HDR_RETRY_AFTER)
    if backoff:
        note += f" · 서버 백오프 요청({backoff}s)"
    return note


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def zotero_search_items(
        q: str | None = None,
        item_type: str | None = None,
        tag: str | None = None,
        limit: int = z.DEFAULT_LIMIT,
        start: int = 0,
        qmode: str | None = None,
    ) -> str:
        """Zotero 라이브러리에서 아이템을 검색/나열한다(GET /{prefix}/items).

        Args:
            q: 검색어. 미지정 시 라이브러리의 상위 아이템을 나열한다.
            item_type: itemType 필터(예: book, journalArticle). 부정은 '-' 접두(예: -attachment).
            tag: 태그 필터.
            limit: 페이지 크기. 기본 25, 최대 100.
            start: 페이지 오프셋(0부터). 다음 페이지는 안내된 start 값을 쓴다.
            qmode: 'titleCreatorYear'(기본) 또는 'everything'(전문 포함 검색).
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
            params = z.build_search_params(
                q=q, item_type=item_type, tag=tag, qmode=qmode, limit=limit, start=start
            )
        except ValueError as e:  # BackendError(상속) + build_search_params 검증 둘 다
            return str(e)

        try:
            body, resp_headers = await get_with_headers(
                f"{base}/{z.items_path(prefix)}", headers=headers, params=params
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return _explain(e, source)

        rows = body if isinstance(body, list) else []
        items = [z.ZoteroItem.model_validate(r) for r in rows if isinstance(r, dict)]
        note = _pagination_note(resp_headers, start, len(items))
        if not items:
            return f"검색 결과 없음. ({note})"
        lines = [note]
        for it in items:
            data = it.data or {}
            title = data.get("title") or data.get("note") or "(제목 없음)"
            itype = data.get("itemType", "?")
            lines.append(f"- [{it.key}] ({itype}) {title}")
        return "\n".join(lines)

    @mcp.tool
    async def zotero_get_item(item_key: str, include: str | None = None) -> str:
        """단일 아이템을 조회한다(GET /{prefix}/items/{itemKey}).

        Args:
            item_key: 아이템 키.
            include: 포함 포맷(예: data,bib,citation). 기본은 data.
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
        except ValueError as e:
            return str(e)

        params = {"include": include} if include else None
        try:
            body = await get_json(
                f"{base}/{z.item_path(prefix, item_key)}", headers=headers, params=params
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return _explain(e, source)

        if not isinstance(body, dict):
            return f"응답: {body}"
        item = z.ZoteroItem.model_validate(body)
        data = item.data or {}
        title = data.get("title") or data.get("note") or "(제목 없음)"
        itype = data.get("itemType", "?")
        return f"[{item.key}] v{item.version} ({itype}) {title}"

    @mcp.tool
    async def zotero_get_item_children(item_key: str) -> str:
        """아이템의 자식(노트/첨부)을 나열한다(GET /{prefix}/items/{itemKey}/children).

        Args:
            item_key: 부모 아이템 키.
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
        except ValueError as e:
            return str(e)

        try:
            body = await get_json(
                f"{base}/{z.item_children_path(prefix, item_key)}", headers=headers
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return _explain(e, source)

        rows = body if isinstance(body, list) else []
        items = [z.ZoteroItem.model_validate(r) for r in rows if isinstance(r, dict)]
        if not items:
            return "자식 아이템 없음."
        lines = [f"자식 {len(items)}건:"]
        for it in items:
            data = it.data or {}
            label = data.get("title") or data.get("note") or data.get("itemType", "?")
            lines.append(f"- [{it.key}] ({data.get('itemType', '?')}) {label}")
        return "\n".join(lines)

    @mcp.tool
    async def zotero_list_collections(top: bool = False) -> str:
        """컬렉션을 나열한다(GET /{prefix}/collections, top=True면 /collections/top).

        Args:
            top: True면 최상위 컬렉션만 나열한다.
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
        except ValueError as e:
            return str(e)

        try:
            body = await get_json(
                f"{base}/{z.collections_path(prefix, top=top)}", headers=headers
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return _explain(e, source)

        rows = body if isinstance(body, list) else []
        cols = [z.Collection.model_validate(r) for r in rows if isinstance(r, dict)]
        if not cols:
            return "컬렉션 없음."
        lines = [f"컬렉션 {len(cols)}건:"]
        for c in cols:
            name = (c.data or {}).get("name", "(이름 없음)")
            lines.append(f"- [{c.key}] {name}")
        return "\n".join(lines)

    @mcp.tool
    async def zotero_get_collection_items(
        collection_key: str, limit: int = z.DEFAULT_LIMIT, start: int = 0
    ) -> str:
        """컬렉션의 아이템을 나열한다(GET /{prefix}/collections/{collectionKey}/items).

        Args:
            collection_key: 컬렉션 키.
            limit: 페이지 크기. 기본 25, 최대 100.
            start: 페이지 오프셋(0부터).
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
            params = z.build_search_params(limit=limit, start=start)
        except ValueError as e:
            return str(e)

        try:
            body, resp_headers = await get_with_headers(
                f"{base}/{z.collection_items_path(prefix, collection_key)}",
                headers=headers,
                params=params,
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return _explain(e, source)

        rows = body if isinstance(body, list) else []
        items = [z.ZoteroItem.model_validate(r) for r in rows if isinstance(r, dict)]
        note = _pagination_note(resp_headers, start, len(items))
        if not items:
            return f"이 컬렉션에 아이템 없음. ({note})"
        lines = [note]
        for it in items:
            data = it.data or {}
            title = data.get("title") or data.get("note") or "(제목 없음)"
            lines.append(f"- [{it.key}] ({data.get('itemType', '?')}) {title}")
        return "\n".join(lines)

    @mcp.tool
    async def zotero_list_tags(limit: int = z.DEFAULT_LIMIT, start: int = 0) -> str:
        """라이브러리의 태그를 나열한다(GET /{prefix}/tags).

        Args:
            limit: 페이지 크기. 기본 25, 최대 100.
            start: 페이지 오프셋(0부터).
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
            params = z.build_search_params(limit=limit, start=start)
        except ValueError as e:
            return str(e)

        try:
            body, resp_headers = await get_with_headers(
                f"{base}/{z.tags_path(prefix)}", headers=headers, params=params
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return _explain(e, source)

        rows = body if isinstance(body, list) else []
        tags = [z.Tag.model_validate(r) for r in rows if isinstance(r, dict)]
        note = _pagination_note(resp_headers, start, len(tags))
        if not tags:
            return f"태그 없음. ({note})"
        return note + "\n" + "\n".join(f"- {t.tag}" for t in tags)

    @mcp.tool
    async def zotero_get_fulltext(item_key: str) -> str:
        """첨부 아이템의 전문(full-text)을 조회한다(GET /{prefix}/items/{itemKey}/fulltext).

        텍스트 문서는 indexedChars/totalChars, PDF는 indexedPages/totalPages를 함께 알려준다.

        Args:
            item_key: 전문이 인덱싱된 첨부 아이템 키.
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
        except ValueError as e:
            return str(e)

        try:
            body = await get_json(
                f"{base}/{z.item_fulltext_path(prefix, item_key)}", headers=headers
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return _explain(e, source)

        if not isinstance(body, dict):
            return f"응답: {body}"
        ft = z.Fulltext.model_validate(body)
        if ft.indexedPages is not None or ft.totalPages is not None:
            meta = f"PDF {ft.indexedPages}/{ft.totalPages} 페이지 인덱싱"
        elif ft.indexedChars is not None or ft.totalChars is not None:
            meta = f"텍스트 {ft.indexedChars}/{ft.totalChars} 문자 인덱싱"
        else:
            meta = "(인덱싱 메타 없음)"
        preview = ft.content if len(ft.content) <= 2000 else ft.content[:2000] + " …(생략)"
        return f"{meta}\n---\n{preview}" if preview else f"{meta} · 전문 콘텐츠 없음."

    @mcp.tool
    async def zotero_health() -> str:
        """백엔드 연결/설정 상태를 점검한다.

        local: base(/)에 접속해 Zotero-API-Version 헤더를 확인한다.
        web: 키/유저(또는 그룹) 설정이 갖춰졌는지 + API 도달 가능 여부를 알린다.
        """
        s = ZoteroSettings()
        try:
            base, prefix, headers, source = _resolve(s)
        except ValueError as e:
            return f"비정상: {e}"

        if source == "local":
            # 로컬 API 루트(<base>/)에 접속 시도. 200/헤더로 활성 확인.
            try:
                _, resp_headers = await get_with_headers(f"{base}/", headers=headers)
            except httpx.ConnectError:
                return _explain_connect(s, source, base)
            except UpstreamError as e:
                # 403이면 비활성 안내, 그 외도 사람이 읽을 메시지.
                return f"local 점검: {_explain(e, source)}"
            ver = resp_headers.get(z.HDR_LAST_MODIFIED_VERSION) or resp_headers.get(
                z.API_VERSION_HEADER.lower()
            )
            return f"정상(local): {base} 응답 · API-Version 헤더={ver or '확인'} · prefix={prefix}"

        # web: 설정 점검 + 실제 한 번 호출(items?limit=1)로 키/권한 도달 확인.
        key_state = "키 있음" if s.api_key else "키 없음(공개 라이브러리만)"
        try:
            body, resp_headers = await get_with_headers(
                f"{base}/{z.items_path(prefix)}",
                headers=headers,
                params={"limit": 1},
            )
        except httpx.ConnectError:
            return _explain_connect(s, source, base)
        except UpstreamError as e:
            return f"web 점검 실패({key_state}, prefix={prefix}): {_explain(e, source)}"
        total = resp_headers.get(z.HDR_TOTAL_RESULTS, "?")
        return f"정상(web): {key_state} · prefix={prefix} · 총 {total}건 접근 가능"
