"""Hacker News 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기·**무인증**.
Firebase(아이템·랭킹·사용자)와 Algolia(검색) 두 공식 API를 합성한다. 둘 다 JSON이라
코어 `get_json`을 쓴다. 인터랙티브 OAuth 아님 → make_auth_client 없음.

⚠️ 랭킹(`hn_top`)은 Firebase가 **id 배열만** 주므로 상위 N개를 개별 fetch한다(N+1).
상한(MAX_RANK_LIMIT)으로 호출 폭증을 막고, `asyncio.gather`로 병렬화한다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.hackernews import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


def _explain(e: UpstreamError) -> str:
    """관측·문서화된 상태코드를 사람이 읽을 메시지로 매핑한다."""
    if e.status == 404:
        return "찾을 수 없습니다(404): id/사용자명을 확인하세요."
    if e.status == 429:
        return "요청 한도 초과(429): 잠시 후 재시도하세요."
    if e.status in (500, 502, 503, 504):
        return f"HN 서버 오류({e.status}): 잠시 후 재시도하세요."
    return f"HN API 오류 {e.status}."


def _fmt_time(ts: int | None) -> str | None:
    """unix timestamp를 'YYYY-MM-DD HH:MM UTC'로 변환한다(없으면 None)."""
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _item_line(it: c.HNItem) -> str:
    """story/job 한 줄 요약: `- title  (N점·댓글 M) by author  [id]`."""
    title = c.clean_html(it.title) or "(제목 없음)"
    meta = []
    if it.score is not None:
        meta.append(f"{it.score}점")
    if it.descendants is not None:
        meta.append(f"댓글 {it.descendants}")
    if it.by:
        meta.append(f"by {it.by}")
    tail = f"  ({' · '.join(meta)})" if meta else ""
    return f"- {title}{tail}  [{it.id}]"


def _hit_line(h: c.AlgoliaHit) -> str:
    """Algolia 검색 결과 한 줄."""
    title = c.clean_html(h.title) or c.clean_html(h.story_text) or "(제목 없음)"
    meta = []
    if h.points is not None:
        meta.append(f"{h.points}점")
    if h.num_comments is not None:
        meta.append(f"댓글 {h.num_comments}")
    if h.author:
        meta.append(f"by {h.author}")
    tail = f"  ({' · '.join(meta)})" if meta else ""
    return f"- {title}{tail}  [{h.objectID}]"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def hn_item(id: int) -> str:
        """Hacker News 아이템(스토리·댓글·잡·폴)을 id로 조회한다(Firebase /v0/item).

        스토리/잡이면 제목·점수·댓글수·작성자·시간·URL(+본문), 댓글이면 본문·작성자·부모를 돌려준다.

        Args:
            id: 아이템 id(정수). 필수. 예: `8863`.
        """
        try:
            raw = await get_json(c.item_url(id))
        except UpstreamError as e:
            return _explain(e)
        if not isinstance(raw, dict) or not raw:
            return "아이템을 찾을 수 없습니다. id를 확인하세요."
        it = c.HNItem.model_validate(raw)
        if it.deleted:
            return f"[{it.id}] 삭제된 아이템입니다."

        when = _fmt_time(it.time)
        if it.type == "comment":
            lines = [f"[{it.id}] 댓글" + (f" by {it.by}" if it.by else "")]
            if when:
                lines.append(when)
            if it.parent:
                lines.append(f"부모: {it.parent} ({c.item_permalink(it.parent)})")
            body = c.clean_html(it.text)
            if body:
                lines.append(body)
            return "\n".join(lines)

        # story / job / poll
        title = c.clean_html(it.title) or "(제목 없음)"
        lines = [f"[{it.id}] {title}"]
        meta = []
        if it.score is not None:
            meta.append(f"{it.score}점")
        if it.descendants is not None:
            meta.append(f"댓글 {it.descendants}")
        if it.by:
            meta.append(f"by {it.by}")
        if when:
            meta.append(when)
        if meta:
            lines.append(" · ".join(meta))
        if it.url:
            lines.append(it.url)
        lines.append(f"HN: {c.item_permalink(it.id)}")
        body = c.clean_html(it.text, limit=500)
        if body:
            lines.append(body)
        return "\n".join(lines)

    @mcp.tool
    async def hn_top(kind: str = "top", limit: int = c.DEFAULT_LIMIT) -> str:
        """Hacker News 프론트페이지 랭킹의 상위 항목을 가져온다(Firebase 랭킹 리스트).

        Args:
            kind: 랭킹 종류 — `top`·`new`·`best`·`ask`·`show`·`job`. 기본 `top`.
            limit: 가져올 항목 수. 기본 10, 1..50(각 항목을 개별 조회하므로 보수적).
        """
        try:
            k = c.validate_ranking(kind)
            n = c.validate_limit(limit, maximum=c.MAX_RANK_LIMIT)
        except ValueError as e:  # 계약 위반은 HTTP 전에 막힌다
            return str(e)

        try:
            ids = await get_json(c.ranking_url(k))
        except UpstreamError as e:
            return _explain(e)
        if not isinstance(ids, list) or not ids:
            return f"랭킹({k})이 비어 있습니다."

        top_ids = ids[:n]
        try:
            raws = await asyncio.gather(*[get_json(c.item_url(i)) for i in top_ids])
        except UpstreamError as e:
            return _explain(e)

        lines = [f"HN {k} 상위 {len(top_ids)}건:"]
        for raw in raws:
            if isinstance(raw, dict) and raw:
                lines.append(_item_line(c.HNItem.model_validate(raw)))
        return "\n".join(lines)

    @mcp.tool
    async def hn_search(
        query: str,
        by_date: bool = False,
        tags: str | None = None,
        limit: int = c.DEFAULT_LIMIT,
    ) -> str:
        """Hacker News를 전문 검색한다(Algolia HN Search).

        Args:
            query: 검색어. 필수.
            by_date: True면 최신순(`/search_by_date`), False면 관련도순(`/search`). 기본 False.
            tags: (선택) Algolia 태그 필터 문자열 그대로 — 예: `story`·`comment`·`ask_hn`·
                `show_hn`·`author_pg`·`story_8863`. 괄호로 OR(`(story,poll)`), 콤마로 AND.
            limit: 결과 수(hitsPerPage). 기본 10, 1..50.
        """
        if not query or not query.strip():
            return "query가 비어 있습니다. 검색어를 입력하세요."
        try:
            n = c.validate_limit(limit, maximum=c.MAX_SEARCH_LIMIT)
        except ValueError as e:
            return str(e)

        params: dict[str, str | int] = {c.PARAM_QUERY: query.strip(), c.PARAM_HITS_PER_PAGE: n}
        if tags and tags.strip():
            params[c.PARAM_TAGS] = tags.strip()
        endpoint = c.ALGOLIA_SEARCH_BY_DATE if by_date else c.ALGOLIA_SEARCH
        try:
            body = await get_json(endpoint, params=params)
        except UpstreamError as e:
            return _explain(e)
        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.AlgoliaResult.model_validate(body)
        if not result.hits:
            return "검색 결과 없음"
        total = result.nbHits if result.nbHits is not None else "?"
        order = "최신순" if by_date else "관련도순"
        lines = [f"총 {total}건 ({order})"]
        lines += [_hit_line(h) for h in result.hits]
        return "\n".join(lines)

    @mcp.tool
    async def hn_user(id: str) -> str:
        """Hacker News 사용자 프로필을 조회한다(Firebase /v0/user).

        Args:
            id: 사용자명(대소문자 구분). 필수. 예: `pg`.
        """
        if not id or not id.strip():
            return "id가 비어 있습니다. 사용자명을 입력하세요."
        try:
            raw = await get_json(c.user_url(id.strip()))
        except UpstreamError as e:
            return _explain(e)
        if not isinstance(raw, dict) or not raw:
            return "사용자를 찾을 수 없습니다. 사용자명을 확인하세요."
        u = c.HNUser.model_validate(raw)
        lines = [f"{u.id}"]
        meta = []
        if u.karma is not None:
            meta.append(f"karma {u.karma}")
        created = _fmt_time(u.created)
        if created:
            meta.append(f"가입 {created}")
        meta.append(f"제출 {len(u.submitted)}건")
        lines.append(" · ".join(meta))
        about = c.clean_html(u.about, limit=500)
        if about:
            lines.append(about)
        return "\n".join(lines)
