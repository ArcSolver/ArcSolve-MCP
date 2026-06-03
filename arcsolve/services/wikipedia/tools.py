"""Wikipedia(위키백과) 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

**무인증**으로 전체 읽기가 동작하지만 Wikimedia는 NWS처럼 식별용 **`User-Agent` 헤더를 요구**한다
(없거나 약하면 403/스로틀). 기본 식별 문자열(contract.DEFAULT_USER_AGENT)을 항상 보내고
`WIKIPEDIA_USER_AGENT`로 덮어쓴다. (선택) `WIKIPEDIA_API_TOKEN`을 주면 `Authorization: Bearer`를
UA와 함께 보내 레이트리밋이 완화된다(토큰 없이도 읽기는 전부 동작).

세 종류 엔드포인트를 섞어 쓴다: ① per-wiki REST 검색(`/w/rest.php/v1/search/page`),
② rest_v1 요약(`/api/rest_v1/page/summary/{title}`), ③ Action API 본문/링크
(`/w/api.php?action=query&prop=extracts` · `prop=links|categories`). 언어판마다 호스트가 달라
`lang`으로 base를 만든다. ⚠️ Action API는 잘못된 파라미터에 **HTTP 200 + `{"error":...}`**를 줄 수
있어 본문을 보고 매핑한다. 헤더는 코어 `get_json(headers=...)`로 주입한다(서비스 폴더에서 httpx
직접 생성 금지 — AGENTS 규칙). 인터랙티브 OAuth가 아니므로 make_auth_client 없음(nws와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, bearer, get_json
from arcsolve.services.wikipedia import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class WikipediaSettings(BaseSettings):
    """WIKIPEDIA_* 환경변수에서 (선택) User-Agent / API 토큰을 로드한다.

    - user_agent: 식별용 User-Agent(선택). Wikimedia는 헤더를 요구하므로 기본값
      (contract.DEFAULT_USER_AGENT)을 항상 보내며, 연락처를 넣고 싶으면 `WIKIPEDIA_USER_AGENT`로
      덮어쓴다.
    - api_token: (선택) Bearer 토큰. 있으면 `Authorization: Bearer {token}`을 UA와 함께 보내
      레이트리밋이 완화된다. 없어도 전체 읽기가 동작한다(무인증).
    """

    model_config = SettingsConfigDict(env_prefix="WIKIPEDIA_", env_file=".env", extra="ignore")
    user_agent: str | None = None
    api_token: str | None = None


def _headers(user_agent: str | None, api_token: str | None) -> dict[str, str]:
    """필수 User-Agent 헤더를 만들고, 토큰이 있으면 Bearer를 덧붙인다.

    Wikimedia는 식별용 User-Agent를 요구하므로 항상 채운다(env 비면 기본 식별 문자열).
    토큰은 선택 — 있으면 레이트리밋 완화. 출처: Wikimedia User-Agent policy + REST API Bearer 인증.
    """
    h = {"User-Agent": user_agent or c.DEFAULT_USER_AGENT}
    if api_token:
        h.update(bearer(api_token))
    return h


def _explain(e: UpstreamError) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    rest_v1/REST 검색은 4xx/5xx로 에러를 준다(요약 404 = 문서 없음). Action API는 잘못된 파라미터에
    HTTP 200 + 본문 error를 주므로(별도 처리), 여기선 전송 계층 상태코드만 매핑한다.
    출처: 라이브(요약 404, 무 UA → 403, 429 스로틀).
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    detail = ""
    if payload:
        # rest_v1 에러 봉투: {"type","title","detail","method","uri"}; Action 비-200은 드묾.
        d = payload.get("detail") or payload.get("title") or payload.get("message")
        if isinstance(d, str) and d.strip():
            detail = f" {d.strip()}"
    if e.status == 400:
        return f"요청 오류(400): 입력 값을 확인하세요.{detail}"
    if e.status == 403:
        return (
            "접근 거부(403): User-Agent 헤더가 필요합니다(WIKIPEDIA_USER_AGENT 설정을 확인하세요)."
        )
    if e.status == 404:
        return "문서를 찾을 수 없습니다(404): 제목/언어를 확인하세요."
    if e.status == 429:
        return (
            "요청 한도 초과(429): 잠시 후 재시도하세요"
            "(Retry-After 권장). WIKIPEDIA_API_TOKEN을 쓰면 레이트리밋이 완화됩니다."
        )
    if e.status in (500, 502, 503, 504):
        return f"Wikipedia 서버 오류({e.status}): 잠시 후 재시도하세요.{detail}"
    # 미매핑 상태코드: dict에서 뽑은 detail만 노출하고, 비-dict 본문(HTML 등)은 원문을 흘리지 않는다.
    return f"Wikipedia API 오류 {e.status}.{detail}"


def _action_error(body: dict) -> str | None:
    """Action API의 HTTP 200 + `{"error":{code,info}}` 봉투를 검사해 메시지를 만든다(없으면 None).

    출처: 라이브(/w/api.php?action=nonsense → 200 {"error":{"code":"badvalue","info":...}}).
    """
    if isinstance(body, dict) and body.get("error"):
        err = c.ActionError.model_validate(body["error"])
        info = (err.info or err.code or "").strip()
        return f"요청 오류: {info}" if info else "요청 오류(Action API)."
    return None


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def wikipedia_search(
        query: str, lang: str = c.DEFAULT_LANG, limit: int = c.DEFAULT_SEARCH_LIMIT
    ) -> str:
        """위키백과에서 문서를 검색한다(클린 REST: GET /w/rest.php/v1/search/page).

        제목·요약·스니펫을 평문으로 돌려준다(구식 Action `list=search`가 아닌 per-wiki REST).

        Args:
            query: 검색어. 필수.
            lang: 언어판 코드(소문자). 기본 `en`. 예: `en`·`ko`·`de`·`zh`·`simple`.
            limit: 결과 개수. 기본 10, 1..100.
        """
        s = WikipediaSettings()
        try:
            code = c.validate_lang(lang)
            c.validate_limit(limit, maximum=c.MAX_SEARCH_LIMIT)
        except ValueError as e:  # 형식/범위 위반은 HTTP 전에 막힌다
            return str(e)

        url = f"{c.wiki_host(code)}{c.REST_SEARCH_PATH}"
        try:
            body = await get_json(
                url,
                params={"q": query, "limit": limit},
                headers=_headers(s.user_agent, s.api_token),
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.SearchResponse.model_validate(body)
        if not result.pages:
            return "검색 결과 없음"
        lines = []
        for p in result.pages:
            head = f"- [{p.key or '?'}] {p.title or '(제목 없음)'}"
            if p.description:
                head += f" — {p.description}"
            lines.append(head)
            snippet = c.strip_html(p.excerpt)
            if snippet:
                lines.append(f"  {snippet}")
        return "\n".join(lines)

    @mcp.tool
    async def wikipedia_summary(title: str, lang: str = c.DEFAULT_LANG) -> str:
        """문서의 lead 요약(extract)을 조회한다(rest_v1: GET /api/rest_v1/page/summary/{title}).

        리다이렉트를 자동 추적한다. 요약·문서 URL·Wikidata Q-id(있으면)·좌표(지리 문서)를 돌려준다.
        동음이의(disambiguation) 문서면 안내를 덧붙인다.

        Args:
            title: 문서 제목(공백/슬래시 그대로 — 경로 인코딩은 내부 처리). 필수.
            lang: 언어판 코드(소문자). 기본 `en`.
        """
        s = WikipediaSettings()
        try:
            code = c.validate_lang(lang)
        except ValueError as e:
            return str(e)

        url = f"{c.wiki_host(code)}{c.summary_path(title)}"
        try:
            body = await get_json(url, headers=_headers(s.user_agent, s.api_token))
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        sm = c.SummaryResponse.model_validate(body)
        head = sm.title or title
        if sm.description:
            head += f" — {sm.description}"
        lines = [head]
        if sm.extract:
            lines.append(sm.extract)
        page_url = (
            sm.content_urls.desktop.page if (sm.content_urls and sm.content_urls.desktop) else None
        )
        if page_url:
            lines.append(f"URL: {page_url}")
        if sm.wikibase_item:
            lines.append(f"Wikidata: {sm.wikibase_item}")
        if sm.coordinates and sm.coordinates.lat is not None and sm.coordinates.lon is not None:
            lines.append(f"좌표: {sm.coordinates.lat}, {sm.coordinates.lon}")
        if sm.type == "disambiguation":
            lines.append("(동음이의 문서입니다 — 더 구체적인 제목으로 다시 조회하세요.)")
        return "\n".join(lines)

    @mcp.tool
    async def wikipedia_extract(
        title: str,
        lang: str = c.DEFAULT_LANG,
        intro_only: bool = True,
        max_chars: int | None = None,
    ) -> str:
        """문서 평문 본문을 조회한다(TextExtracts: GET /w/api.php?action=query&prop=extracts).

        리다이렉트를 추적하고, 기본은 도입부(intro)만 평문으로 돌려준다.

        Args:
            title: 문서 제목. 필수.
            lang: 언어판 코드(소문자). 기본 `en`.
            intro_only: True면 도입부만(exintro). False면 전체 본문. 기본 True.
            max_chars: 글자 수 제한(exchars, 1..1200). 미지정 시 제한 없음.
        """
        s = WikipediaSettings()
        try:
            code = c.validate_lang(lang)
            if max_chars is not None:
                c.validate_exchars(max_chars)
        except ValueError as e:
            return str(e)

        url = f"{c.wiki_host(code)}{c.ACTION_API_PATH}"
        params = c.extracts_params(title, intro_only=intro_only, max_chars=max_chars)
        try:
            body = await get_json(url, params=params, headers=_headers(s.user_agent, s.api_token))
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        action_err = _action_error(body)
        if action_err:
            return action_err
        pages = (body.get("query") or {}).get("pages") or []
        if not pages:
            return "문서를 찾을 수 없습니다"
        page = c.ExtractPage.model_validate(pages[0])
        if page.missing:
            return "문서를 찾을 수 없습니다"
        if not page.extract:
            return f"{page.title or title}: (본문 없음)"
        return f"{page.title or title}\n{page.extract}"

    @mcp.tool
    async def wikipedia_links(
        title: str, lang: str = c.DEFAULT_LANG, limit: int = c.DEFAULT_LINKS_LIMIT
    ) -> str:
        """문서의 나가는 링크와 분류를 조회한다(Action API: prop=links|categories).

        문서(ns 0) 링크 제목과 분류(category)를 나열한다.

        Args:
            title: 문서 제목. 필수.
            lang: 언어판 코드(소문자). 기본 `en`.
            limit: 링크/분류 각 최대 개수. 기본 50, 1..500.
        """
        s = WikipediaSettings()
        try:
            code = c.validate_lang(lang)
            c.validate_limit(limit, maximum=c.MAX_LINKS_LIMIT)
        except ValueError as e:
            return str(e)

        url = f"{c.wiki_host(code)}{c.ACTION_API_PATH}"
        params = c.links_params(title, limit=limit)
        try:
            body = await get_json(url, params=params, headers=_headers(s.user_agent, s.api_token))
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        action_err = _action_error(body)
        if action_err:
            return action_err
        pages = (body.get("query") or {}).get("pages") or []
        if not pages:
            return "문서를 찾을 수 없습니다"
        page = c.LinksPage.model_validate(pages[0])
        if page.missing:
            return "문서를 찾을 수 없습니다"

        lines = [page.title or title]
        if page.links:
            lines.append(f"연결 문서 {len(page.links)}개:")
            lines += [f"- {ln.title}" for ln in page.links if ln.title]
        else:
            lines.append("연결 문서: 없음")
        if page.categories:
            lines.append(f"분류 {len(page.categories)}개:")
            lines += [f"- {cat.title}" for cat in page.categories if cat.title]
        else:
            lines.append("분류: 없음")
        return "\n".join(lines)
