"""Open-Meteo 날씨·기후 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

**무인증**(키 없음·env 불필요). 식별용 User-Agent만 전송한다. 페이지네이션·헤더 동사가 필요 없는
단발 조회라 코어 `get_json`만 쓴다. 인터랙티브 OAuth가 아니므로 make_auth_client 없음
(crossref/arxiv와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.openmeteo import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


def _user_agent() -> dict[str, str]:
    """식별용 User-Agent 헤더(무인증이라 인증 헤더는 없음)."""
    return {"User-Agent": "arcsolve/openmeteo (https://github.com/ArcSolver/ArcSolve-Kit)"}


def _explain(e: UpstreamError) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    Open-Meteo 에러 봉투는 `{"error": true, "reason": "..."}`(HTTP 400) — reason만 노출한다.
    payload가 dict가 아니면(비-JSON) 원문을 노출하지 않는다.
    출처: 예보 문서 (에러 응답) + 라이브 (/forecast?latitude=52.52 → 400 {"reason":...,"error":true})
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    reason = payload.get("reason") if payload else None
    detail = f" {reason.strip()}" if reason else ""
    if e.status == 400:
        return f"요청 오류(400): 좌표/변수명/파라미터를 확인하세요.{detail}"
    if e.status == 429:
        return "요청 한도 초과(429): 잠시 후 재시도하세요(무료 풀의 일일/분당 한도)."
    return f"Open-Meteo API 오류 {e.status}:{detail}"


def _geocode_line(r: c.GeocodingResult) -> str:
    """지오코딩 결과 1줄: `- name, admin1, country (lat, lon) · TZ tz`."""
    parts = [r.name or "(이름 없음)"]
    if r.admin1:
        parts.append(r.admin1)
    if r.country:
        parts.append(r.country)
    where = ", ".join(parts)
    lat = f"{r.latitude:.4f}" if r.latitude is not None else "?"
    lon = f"{r.longitude:.4f}" if r.longitude is not None else "?"
    tz = f" · TZ {r.timezone}" if r.timezone else ""
    return f"- {where} ({lat}, {lon}){tz}"


def _series_block(label: str, series: dict | None, units: dict | None, limit: int = 6) -> list[str]:
    """hourly/daily 시계열 dict를 사람이 읽을 몇 줄로 요약한다.

    `{time:[...], <변수>:[...]}` 구조에서 time과 각 변수의 앞 `limit`개만 표시한다(응답이 길 수 있어 절단).
    """
    if not series or "time" not in series:
        return []
    times = series.get("time") or []
    lines = [f"{label} (앞 {min(limit, len(times))}개 / 총 {len(times)}개):"]
    var_names = [k for k in series if k != "time"]
    for i, t in enumerate(times[:limit]):
        cells = []
        for v in var_names:
            vals = series.get(v) or []
            val = vals[i] if i < len(vals) else "?"
            unit = (units or {}).get(v, "")
            cells.append(f"{v}={val}{unit}")
        lines.append(f"  {t}: " + ", ".join(cells))
    return lines


def _current_block(current: dict | None, units: dict | None) -> list[str]:
    """current dict를 사람이 읽을 몇 줄로 요약한다.

    `{time, interval, <변수>:value}` — time/interval을 제외한 변수만 값으로 표시한다.
    """
    if not current:
        return []
    t = current.get("time", "?")
    lines = [f"현재({t}):"]
    for k, v in current.items():
        if k in ("time", "interval"):
            continue
        unit = (units or {}).get(k, "")
        lines.append(f"  {k} = {v}{unit}")
    return lines


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def openmeteo_geocode(
        name: str,
        count: int = c.GEOCODING_DEFAULT_COUNT,
        language: str | None = None,
    ) -> str:
        """지명을 좌표·국가·시간대로 변환한다(GET geocoding-api /v1/search).

        다른 도구(`openmeteo_forecast`)의 latitude/longitude 입력을 보조한다.

        Args:
            name: 검색할 지명. 2자는 정확 매칭, 3자 이상은 퍼지 매칭이다.
            count: 최대 결과 수. 기본 10, 1..100.
            language: 결과 언어(소문자 ISO 코드, 예 `en`/`ko`). 미지정 시 상류 기본 `en`.
        """
        try:
            params = c.build_geocoding_params(name=name, count=count, language=language)
        except ValueError as e:  # count 범위 위반은 HTTP 전에 막힌다
            return str(e)

        try:
            body = await get_json(
                f"{c.GEOCODING_BASE_URL}{c.GEOCODING_SEARCH}",
                params=params,
                headers=_user_agent(),
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        result = c.GeocodingResponse.model_validate(body)
        if not result.results:
            return f"검색 결과 없음: {name!r}"
        lines = [f"'{name}' 검색 결과 {len(result.results)}건:"]
        lines.extend(_geocode_line(r) for r in result.results)
        return "\n".join(lines)

    @mcp.tool
    async def openmeteo_forecast(
        latitude: float,
        longitude: float,
        hourly: str | None = None,
        daily: str | None = None,
        current: str | None = None,
        timezone: str | None = None,
        forecast_days: int = c.FORECAST_DEFAULT_DAYS,
    ) -> str:
        """좌표의 날씨 예보를 조회한다(GET api /v1/forecast).

        hourly/daily/current는 **콤마 구분 변수명 문자열**로 받아 그대로 전달한다
        (예: `temperature_2m,precipitation`). 변수명 검증은 상류가 수행한다.

        Args:
            latitude: 위도(WGS84). 필수.
            longitude: 경도(WGS84). 필수.
            hourly: 시간별 변수(콤마 구분). 예 `temperature_2m,precipitation,wind_speed_10m`.
            daily: 일별 변수(콤마 구분). 예 `temperature_2m_max,temperature_2m_min,precipitation_sum`.
            current: 현재 변수(콤마 구분). 예 `temperature_2m,weather_code`.
            timezone: IANA 시간대 이름 또는 `auto`. 미지정 시 상류 기본 GMT.
            forecast_days: 예보 일수. 기본 7, 0..16.
        """
        try:
            params = c.build_forecast_params(
                latitude=latitude,
                longitude=longitude,
                hourly=hourly,
                daily=daily,
                current=current,
                timezone=timezone,
                forecast_days=forecast_days,
            )
        except ValueError as e:  # forecast_days 범위 위반은 HTTP 전에 막힌다
            return str(e)

        try:
            body = await get_json(
                f"{c.FORECAST_BASE_URL}{c.FORECAST}",
                params=params,
                headers=_user_agent(),
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        r = c.ForecastResponse.model_validate(body)
        lat = f"{r.latitude:.4f}" if r.latitude is not None else "?"
        lon = f"{r.longitude:.4f}" if r.longitude is not None else "?"
        header = f"예보 ({lat}, {lon})"
        if r.timezone:
            header += f" · {r.timezone}"
        if r.elevation is not None:
            header += f" · 고도 {r.elevation}m"
        lines = [header]
        lines.extend(_current_block(r.current, r.current_units))
        lines.extend(_series_block("시간별", r.hourly, r.hourly_units))
        lines.extend(_series_block("일별", r.daily, r.daily_units))
        if len(lines) == 1:
            lines.append("(hourly/daily/current 중 하나 이상을 지정하세요.)")
        return "\n".join(lines)
