"""RSS/Atom/RDF 피드 읽기 MCP 도구 + 런타임 배선.

contract.py의 파서를 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기·**무인증**.
피드는 XML이므로 코어 `get_text`(raw str)로 받고 contract.parse_feed로 표준 라이브러리 파싱한다.
인터랙티브 OAuth 아님 → make_auth_client 없음(arxiv와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import ParseError

from arcsolve.http import UpstreamError, get_text
from arcsolve.services.feeds import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


def _user_agent() -> dict[str, str]:
    """식별용 User-Agent 헤더(무인증이지만 식별은 예의 — 일부 피드는 UA 없으면 403)."""
    return {"User-Agent": "ArcSolve-MCP/feeds (https://github.com/ArcSolver/ArcSolve-Kit)"}


def _explain(e: UpstreamError) -> str:
    """관측·문서화된 상태코드를 사람이 읽을 메시지로 매핑한다."""
    if e.status == 404:
        return "피드를 찾을 수 없습니다(404): URL을 확인하세요."
    if e.status in (401, 403):
        return f"접근 거부({e.status}): 비공개이거나 인증이 필요한 피드입니다."
    if e.status in (500, 502, 503, 504):
        return f"피드 서버 오류({e.status}): 잠시 후 재시도하세요."
    return f"피드 요청 오류 {e.status}."


def _is_http_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def feeds_fetch(url: str, limit: int = c.DEFAULT_ITEM_LIMIT) -> str:
        """RSS/Atom/RDF 피드를 가져와 메타와 최근 항목을 요약한다.

        임의의 뉴스·블로그·릴리스노트·팟캐스트·YouTube 채널 피드를 표준 포맷으로 읽는다.
        포맷(RSS 2.0 / Atom 1.0 / RSS 1.0·RDF)은 루트 엘리먼트로 자동 감지한다.

        Args:
            url: 피드 URL(http/https). 필수. 예: `https://news.example.com/rss`.
            limit: 가져올 항목 수. 기본 20, 1..100.
        """
        if not url or not url.strip():
            return "url이 비어 있습니다. 피드 URL(http/https)을 입력하세요."
        url = url.strip()
        if not _is_http_url(url):
            return "url은 http:// 또는 https://로 시작해야 합니다."
        try:
            n = c.validate_limit(limit)
        except ValueError as e:  # 범위 위반은 HTTP 전에 막힌다
            return str(e)

        try:
            xml = await get_text(url, headers=_user_agent())
        except UpstreamError as e:
            return _explain(e)
        try:
            feed = c.parse_feed(xml)
        except ParseError:
            return "응답 파싱 실패: 올바른 RSS/Atom XML이 아닙니다."
        except ValueError as e:  # 알 수 없는 루트 포맷
            return str(e)

        head = feed.title or "(제목 없는 피드)"
        lines = [f"{head}  [{feed.format}]"]
        if feed.link:
            lines.append(f"URL: {feed.link}")
        if feed.description:
            lines.append(feed.description)
        if not feed.items:
            lines.append("\n항목 없음")
            return "\n".join(lines)

        shown = feed.items[:n]
        lines.append(f"\n항목 {len(shown)}개 (전체 {len(feed.items)}):")
        for it in shown:
            row = f"- {it.title or '(제목 없음)'}"
            if it.published:
                row += f"  ({it.published})"
            lines.append(row)
            if it.link:
                lines.append(f"  {it.link}")
            if it.summary:
                lines.append(f"  {it.summary}")
        return "\n".join(lines)
