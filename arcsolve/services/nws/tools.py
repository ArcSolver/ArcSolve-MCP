"""NWS(National Weather Service) 미국 날씨 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

**무인증**(키 없음)이지만 NWS는 **`User-Agent` 헤더가 필수**다(없으면 403). 헤더는 코어
`get_json(headers=...)`로 주입한다(서비스 폴더에서 httpx 직접 생성 금지 — AGENTS 규칙). 기본
User-Agent는 contract.DEFAULT_USER_AGENT, 연락처를 덧붙이고 싶으면 `NWS_USER_AGENT`로 덮어쓴다.

예보는 NWS 특유의 **2단계 조회**다: ① `/points/{lat},{lon}`로 office/grid를 얻고 →
② `/gridpoints/{office}/{x},{y}/forecast`(또는 `.../forecast/hourly`)를 조회한다. 미국 밖 좌표는
①에서 404(`InvalidPoint`)로 막히며, 이를 "미국 좌표만 유효" 안내로 매핑한다. 응답은 GeoJSON이고
콘텐츠는 본문 `properties`/`features`에 실리므로 코어 `get_json`만 쓴다. 인터랙티브 OAuth가
아니므로 make_auth_client 없음(crossref/openalex와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.nws import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class NWSSettings(BaseSettings):
    """NWS_* 환경변수에서 (선택) User-Agent를 로드한다.

    - user_agent: 식별용 User-Agent(선택). NWS는 헤더가 필수라 기본값(contract.DEFAULT_USER_AGENT)을
      항상 보내지만, 연락처를 넣고 싶으면 `NWS_USER_AGENT`로 덮어쓴다. 무인증(키 없음).
    """

    model_config = SettingsConfigDict(env_prefix="NWS_", env_file=".env", extra="ignore")
    user_agent: str | None = None


def _headers(user_agent: str | None) -> dict[str, str]:
    """필수 User-Agent 헤더를 만든다. env가 비었으면 기본 식별 문자열을 쓴다.

    NWS는 User-Agent가 없으면 403을 준다(라이브 확인) → 항상 채운다.
    출처: API 안내 ("A User Agent is required to identify your application").
    """
    return {"User-Agent": user_agent or c.DEFAULT_USER_AGENT}


def _explain(e: UpstreamError, *, point: bool = False) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    NWS 에러는 RFC 7807 problem+json `{type,title,status,detail}`이다. point=True(좌표 단계)에서의
    404는 미국 밖 좌표(`InvalidPoint`)를 뜻하므로 별도 안내로 매핑한다.
    출처: 라이브 (/points/<해외> → 404 InvalidPoint, /alerts/active?area=<bad> → 400 BadRequest).
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    detail = ""
    if payload:
        d = payload.get("detail") or payload.get("title")
        if isinstance(d, str) and d.strip():
            detail = f" {d.strip()}"
    if e.status == 404 and point:
        return (
            "해당 좌표의 예보를 제공할 수 없습니다(404): NWS는 미국(+속령) 좌표만 지원합니다. "
            "미국 내 위도/경도인지 확인하세요."
        )
    if e.status == 400:
        return f"요청 오류(400): 좌표/area 값을 확인하세요.{detail}"
    if e.status == 404:
        return f"찾을 수 없음(404): 좌표 또는 그리드를 확인하세요.{detail}"
    if e.status == 403:
        return "접근 거부(403): User-Agent 헤더가 필요합니다(NWS_USER_AGENT 설정을 확인하세요)."
    if e.status == 429:
        return f"요청 한도 초과(429): 잠시 후 재시도하세요.{detail}"
    if e.status in (500, 502, 503, 504):
        return f"NWS 서버 오류({e.status}): 잠시 후 재시도하세요.{detail}"
    return f"NWS API 오류 {e.status}:{detail}"


def _period_line(p: c.ForecastPeriod) -> str:
    """예보 기간 1줄: `- 이름: 온도°단위, 바람 방향 속도 — shortForecast`."""
    temp = f"{p.temperature}°{p.temperature_unit}" if p.temperature is not None else "?"
    wind = " ".join(x for x in [p.wind_direction, p.wind_speed] if x) or "?"
    name = p.name or (p.start_time or "?")
    short = p.short_forecast or "?"
    return f"- {name}: {temp}, 바람 {wind} — {short}"


async def _resolve_point(lat: float, lon: float, ua: str | None) -> c.PointProperties:
    """1단계: 좌표를 office/grid로 변환한다(GET /points/{lat},{lon}). 실패는 UpstreamError로 전파."""
    body = await get_json(
        f"{c.BASE_URL}{c.points_path(lat, lon)}", headers=_headers(ua)
    )
    return c.PointResponse.model_validate(body).properties


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    async def _forecast(latitude: float, longitude: float, *, hourly: bool) -> str:
        """예보 2단계 조회 공통 구현(예보/시간별 예보가 공유)."""
        s = NWSSettings()
        try:
            c.validate_latitude(latitude)
            c.validate_longitude(longitude)
        except ValueError as e:  # 범위 위반은 HTTP 전에 막힌다
            return str(e)

        # ① 좌표 → office/grid
        try:
            point = await _resolve_point(latitude, longitude, s.user_agent)
        except UpstreamError as e:
            return _explain(e, point=True)
        if not (point.grid_id and point.grid_x is not None and point.grid_y is not None):
            return "그리드 정보를 확인할 수 없습니다(좌표를 다시 확인하세요)."

        # ② office/grid → 예보
        path = c.gridpoint_forecast_path(
            point.grid_id, point.grid_x, point.grid_y, hourly=hourly
        )
        try:
            body = await get_json(f"{c.BASE_URL}{path}", headers=_headers(s.user_agent))
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        fc = c.ForecastResponse.model_validate(body).properties
        periods = fc.periods
        kind = "시간별 예보" if hourly else "예보"
        head = f"{point.grid_id} 그리드 {point.grid_x},{point.grid_y} {kind}"
        if not periods:
            return f"{head}: 예보 기간이 없습니다."
        return head + "\n" + "\n".join(_period_line(p) for p in periods)

    @mcp.tool
    async def nws_forecast(latitude: float, longitude: float) -> str:
        """미국 좌표의 다단계(12시간 주야) 예보를 조회한다(2단계: /points → /gridpoints).

        먼저 `/points/{lat},{lon}`로 발령 오피스·그리드를 얻고, 그 그리드의
        `/gridpoints/{office}/{x},{y}/forecast`를 조회한다. 기간별로 이름(Today/Tonight 등)·
        온도·바람·요약(shortForecast)을 돌려준다. **미국(+속령) 좌표만 유효**하다(해외는 404 안내).

        Args:
            latitude: 위도(-90..90). 예: 38.8894(워싱턴 DC).
            longitude: 경도(-180..180). 예: -77.0352.
        """
        return await _forecast(latitude, longitude, hourly=False)

    @mcp.tool
    async def nws_hourly_forecast(latitude: float, longitude: float) -> str:
        """미국 좌표의 시간별 예보를 조회한다(2단계: /points → /gridpoints/.../forecast/hourly).

        `nws_forecast`와 동일한 2단계 패턴이며, 시간 단위 기간을 돌려준다.
        **미국(+속령) 좌표만 유효**하다(해외는 404 안내).

        Args:
            latitude: 위도(-90..90).
            longitude: 경도(-180..180).
        """
        return await _forecast(latitude, longitude, hourly=True)

    @mcp.tool
    async def nws_alerts(area: str) -> str:
        """미국 주(state)의 활성 기상특보를 조회한다(GET /alerts/active?area={ST}).

        2글자 주/속령 코드(예: CA·TX·NY·FL·DC·PR)로 현재 발효 중인 특보(event·severity·
        영향 지역·만료 시각)를 나열한다.

        Args:
            area: 미국 2글자 주/속령 코드(대소문자 무관). 예: `CA`, `TX`, `PR`.
        """
        s = NWSSettings()
        try:
            code = c.validate_area(area)
        except ValueError as e:  # 잘못된 코드는 HTTP 전에 막힌다
            return str(e)

        try:
            body = await get_json(
                f"{c.BASE_URL}{c.ALERTS_ACTIVE}",
                params={"area": code},
                headers=_headers(s.user_agent),
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.AlertsResponse.model_validate(body)
        alerts = result.features
        if not alerts:
            return f"{code}: 현재 활성 기상특보가 없습니다."
        lines = [f"{code}: 활성 특보 {len(alerts)}건"]
        for f in alerts:
            p = f.properties
            sev = f"[{p.severity}]" if p.severity else ""
            where = f" — {p.area_desc}" if p.area_desc else ""
            lines.append(f"- {sev} {p.event or '(특보)'}{where}")
            if p.expires:
                lines.append(f"  만료: {p.expires}")
        return "\n".join(lines)
