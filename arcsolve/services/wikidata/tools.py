"""Wikidata 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

**무인증**(키 없음)이지만 Wikimedia는 **식별 가능한 `User-Agent`가 필수**다(없으면 403/스로틀,
WDQS가 특히 엄격). 헤더는 코어 `get_json(headers=...)`로 주입한다(서비스 폴더에서 httpx 직접
생성 금지 — AGENTS 규칙). 기본 User-Agent는 contract.DEFAULT_USER_AGENT, `WIKIDATA_USER_AGENT`로
덮어쓴다. (선택) `WIKIDATA_API_TOKEN`이 있으면 Bearer로 보내 레이트리밋을 완화한다(읽기는 토큰
없이도 동작).

세 종류의 상류를 쓴다: Action API(`wbsearchentities` 검색)·Wikibase REST v1(엔티티·statements)·
WDQS(SPARQL). Action API는 잘못된 파라미터에도 HTTP 200으로 `error` 봉투를 줄 수 있어 본문에서
별도 확인한다. WDQS는 최대 60초까지 허용하므로 코어 기본 10초 대신 timeout=60을 넘긴다.
인터랙티브 OAuth가 아니므로 make_auth_client 없음(nws/semanticscholar와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, bearer, get_json
from arcsolve.services.wikidata import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피

# WDQS는 쿼리당 최대 60초까지 허용한다(코어 기본 10초로는 부족). 출처: WDQS User Manual.
SPARQL_TIMEOUT = 60.0
# SPARQL 결과를 출력에 표시할 최대 행 수(과다 출력 방지). 초과분은 안내만 한다.
SPARQL_MAX_DISPLAY_ROWS = 50


class WikidataSettings(BaseSettings):
    """WIKIDATA_* 환경변수에서 (선택) User-Agent / API 토큰을 로드한다.

    - user_agent: 식별용 User-Agent(선택). Wikimedia는 식별 가능한 UA가 필수라
      기본값(contract.DEFAULT_USER_AGENT)을 항상 보내며, 연락처를 넣고 싶으면
      `WIKIDATA_USER_AGENT`로 덮어쓴다.
    - api_token: (선택) Bearer 토큰. 있으면 레이트리밋이 완화된다. 읽기는 토큰 없이도 동작.
    """

    model_config = SettingsConfigDict(env_prefix="WIKIDATA_", env_file=".env", extra="ignore")
    user_agent: str | None = None
    api_token: str | None = None


def _headers(user_agent: str | None, api_token: str | None) -> dict[str, str]:
    """헤더를 만든다. User-Agent는 항상(필수), Bearer는 토큰이 있을 때만.

    Wikimedia는 식별 가능한 User-Agent가 없으면 403/스로틀로 막는다 → 항상 채운다.
    출처: WDQS User Manual(User-Agent 정책) + REST API(Bearer 인증).
    """
    headers = {"User-Agent": user_agent or c.DEFAULT_USER_AGENT}
    if api_token:
        headers.update(bearer(api_token))
    return headers


def _explain(e: UpstreamError, *, sparql: bool = False) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    REST 에러는 JSON `{code,message}`이지만 WDQS 구문 오류(400)는 텍스트/자바 예외 본문이 온다 →
    **원문(HTML/스택트레이스)을 노출하지 않는다**. sparql=True면 SPARQL 전용 안내를 덧붙인다.
    출처: REST API(에러 봉투) + WDQS User Manual(400 구문 오류·429 레이트리밋·5xx).
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    detail = ""
    if payload:
        d = payload.get("message") or payload.get("info") or payload.get("error")
        if isinstance(d, str) and d.strip():
            detail = f" {d.strip()}"
    if e.status == 400:
        if sparql:
            # WDQS 400은 자바 예외/HTML 본문이라 원문을 노출하지 않는다.
            return "SPARQL 구문 오류(400): 쿼리 문법을 확인하세요."
        return f"요청 오류(400): id/파라미터를 확인하세요.{detail}"
    if e.status == 403:
        return (
            "접근 거부(403): 식별 가능한 User-Agent가 필요합니다"
            "(WIKIDATA_USER_AGENT 설정을 확인하세요)."
        )
    if e.status == 404:
        return "엔티티를 찾을 수 없습니다(404): id를 확인하세요."
    if e.status == 429:
        msg = "요청 한도 초과(429): 잠시 후 재시도하세요."
        if sparql:
            msg += " WDQS는 동시 5쿼리·쿼리당 60초로 제한됩니다."
        return msg + detail
    if e.status in (500, 502, 503, 504):
        base = "WDQS 서버 오류" if sparql else "Wikidata 서버 오류"
        return f"{base}({e.status}): 잠시 후 재시도하세요.{detail}"
    # 미매핑 상태코드: dict에서 뽑은 detail만 노출하고, 비-dict 본문(HTML/스택트레이스)은 흘리지 않는다.
    return f"Wikidata API 오류 {e.status}.{detail}"


def _pick_lang(values: dict[str, str], language: str) -> str | None:
    """다국어 dict에서 language를 우선 고르고 없으면 en으로 폴백한다(둘 다 없으면 None)."""
    if not values:
        return None
    return values.get(language) or values.get("en")


def _render_value(value: c.StatementValue | None) -> str:
    """statement value를 한 줄에 들어갈 compact 문자열로 렌더링한다.

    - novalue/somevalue → "(값 없음)"/"(미상)"
    - content가 str(예: "Qxx"·문자열) → 그대로
    - content가 dict → data_type별 핵심 키만(time→time, quantity→amount[ unit],
      monolingualtext→text). **P/Q 라벨은 별도 호출 없이 raw id 그대로** 둔다(1콜 원칙).
    """
    if value is None:
        return "(값 없음)"
    if value.type == "novalue":
        return "(값 없음)"
    if value.type == "somevalue":
        return "(미상)"
    content = value.content
    if content is None:
        return "(값 없음)"
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        # time → ISO 시각 문자열
        if "time" in content:
            return str(content.get("time"))
        # quantity → amount[ unit]
        if "amount" in content:
            amount = str(content.get("amount"))
            unit = content.get("unit")
            if unit and unit != "1":  # "1"은 단위 없음(dimensionless)
                return f"{amount} {unit}"
            return amount
        # monolingualtext → text
        if "text" in content:
            return str(content.get("text"))
        # globe-coordinate 등 기타 dict
        return str(content)
    return str(content)


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def wikidata_search(
        query: str,
        language: str = "en",
        type: str = "item",  # noqa: A002
        limit: int = c.DEFAULT_SEARCH_LIMIT,
    ) -> str:
        """Wikidata에서 엔티티를 검색한다(Action API wbsearchentities).

        라벨/별칭으로 매칭해 id·label·description을 돌려준다. item(Q…)·property(P…)·lexeme 등
        타입을 지정할 수 있다.

        Args:
            query: 검색어(라벨/별칭). 필수.
            language: 라벨·설명 언어 코드(예: `en`·`ko`). 기본 `en`.
            type: 검색 대상 타입. `item`(기본)·`property`·`lexeme`·`form`·`sense`.
            limit: 결과 개수(1..50). 기본 7.
        """
        s = WikidataSettings()
        try:
            c.validate_search_type(type)
            c.validate_search_limit(limit)
        except ValueError as e:  # 타입/limit 위반은 HTTP 전에 막힌다
            return str(e)

        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": language,
            "type": type,
            "limit": limit,
            "format": "json",
        }
        try:
            body = await get_json(
                c.ACTION_API_URL,
                params=params,
                headers=_headers(s.user_agent, s.api_token),
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.SearchResponse.model_validate(body)
        # Action API는 HTTP 200으로 error 봉투를 줄 수 있다.
        if result.error:
            info = result.error.get("info") or result.error.get("code") or "알 수 없는 오류"
            return f"검색 오류: {info}"
        if not result.search:
            return "검색 결과 없음"
        lines = []
        for ent in result.search:
            label = ent.label or "(라벨 없음)"
            desc = f" — {ent.description}" if ent.description else ""
            lines.append(f"- [{ent.id or '?'}] {label}{desc}")
        return "\n".join(lines)

    @mcp.tool
    async def wikidata_entity(id: str, language: str = "en") -> str:  # noqa: A002
        """단일 엔티티(item Q… 또는 property P…)를 조회한다(REST v1 /entities).

        라벨·설명·별칭·statement 개수, item이면 영어 위키백과 sitelink를 돌려준다.

        Args:
            id: 엔티티 id. item은 `Q42`, property는 `P31` 형식.
            language: 라벨·설명을 고를 언어 코드(없으면 en으로 폴백). 기본 `en`.
        """
        s = WikidataSettings()
        try:
            eid = c.validate_entity_id(id)
        except ValueError as e:  # 잘못된 id 형식은 HTTP 전에 막힌다
            return str(e)

        path = c.property_path(eid) if c.is_property_id(eid) else c.item_path(eid)
        try:
            body = await get_json(
                f"{c.REST_API_BASE}{path}",
                headers=_headers(s.user_agent, s.api_token),
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        ent = c.RestEntity.model_validate(body)
        label = _pick_lang(ent.labels, language) or "(라벨 없음)"
        lines = [f"[{ent.id or eid}] {label}"]
        desc = _pick_lang(ent.descriptions, language)
        if desc:
            lines.append(f"- 설명: {desc}")
        aliases = ent.aliases.get(language) or ent.aliases.get("en") or []
        if aliases:
            lines.append(f"- 별칭: {', '.join(aliases[:5])}")
        lines.append(f"- statement 속성 수: {len(ent.statements)}")
        enwiki = ent.sitelinks.get("enwiki")
        if enwiki and (enwiki.title or enwiki.url):
            title = enwiki.title or ""
            url = f" ({enwiki.url})" if enwiki.url else ""
            lines.append(f"- 영어 위키백과: {title}{url}")
        return "\n".join(lines)

    @mcp.tool
    async def wikidata_statements(id: str, property: str | None = None) -> str:  # noqa: A002
        """item의 statements(속성→값)를 조회한다(REST v1 /entities/items/{id}/statements).

        property를 주면 해당 속성만 조회한다. 값은 raw id/문자열로 렌더링한다(P/Q 라벨은
        별도 호출 없이 그대로 — 1콜 원칙).

        Args:
            id: item id(`Q42` 형식).
            property: (선택) 특정 속성만 필터(`P31` 형식).
        """
        s = WikidataSettings()
        try:
            qid = c.validate_item_id(id)
            pid = c.validate_property_id(property) if property else None
        except ValueError as e:  # 잘못된 id 형식은 HTTP 전에 막힌다
            return str(e)

        params = {"property": pid} if pid else None
        try:
            body = await get_json(
                f"{c.REST_API_BASE}{c.item_statements_path(qid)}",
                params=params,
                headers=_headers(s.user_agent, s.api_token),
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        # 응답은 property id → [statement] 형태의 dict.
        if not body:
            return "statement가 없습니다"
        lines = []
        for prop_id, raw_statements in body.items():
            statements = [c.Statement.model_validate(st) for st in raw_statements]
            rendered = ", ".join(_render_value(st.value) for st in statements)
            lines.append(f"{prop_id}: {rendered}")
        return "\n".join(lines)

    @mcp.tool
    async def wikidata_sparql(query: str, limit: int | None = None) -> str:
        """WDQS에 SPARQL 쿼리를 실행한다(GET /sparql, format=json).

        쿼리는 변형하지 않고 그대로 보낸다. `limit`은 **표시 행 수만** 제한한다(쿼리 자체는
        변경하지 않음). 헤더 + 변수별 값으로 결과를 표 형태로 돌려준다.

        Args:
            query: SPARQL 쿼리 문자열(예: `SELECT ?item WHERE {...} LIMIT 10`).
            limit: (선택) 표시할 최대 행 수. 미지정 시 최대 50행까지 표시.
        """
        s = WikidataSettings()
        try:
            body = await get_json(
                c.SPARQL_URL,
                params={"query": query, "format": "json"},
                headers=_headers(s.user_agent, s.api_token),
                timeout=SPARQL_TIMEOUT,  # WDQS는 최대 60초 허용(코어 기본 10초로는 부족)
            )
        except UpstreamError as e:
            return _explain(e, sparql=True)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.SparqlResponse.model_validate(body)
        variables = result.head.vars
        bindings = result.results.bindings
        if not bindings:
            return "결과 행이 없습니다"

        # 표시 상한: 사용자 limit과 SPARQL_MAX_DISPLAY_ROWS 중 작은 값.
        cap = SPARQL_MAX_DISPLAY_ROWS
        if limit is not None and limit < cap:
            cap = max(limit, 0)
        shown = bindings[:cap]

        lines = [" | ".join(variables)]
        for row in shown:
            cells = [_render_binding(row.get(v)) for v in variables]
            lines.append(" | ".join(cells))
        if len(bindings) > len(shown):
            lines.append(f"({len(bindings)}행 중 {len(shown)}행 표시)")
        return "\n".join(lines)


def _render_binding(cell: dict[str, Any] | None) -> str:
    """SPARQL binding 한 셀({type,value,...})에서 value 문자열만 뽑는다(없으면 빈칸)."""
    if not cell:
        return ""
    return str(cell.get("value", ""))
