"""USGS FDSN Event Web Service 지진 정보 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

**무인증**(키 없음·env 불필요). 식별용 User-Agent만 전송한다. 응답은 `format=geojson` 고정 →
검색은 GeoJSON FeatureCollection, 건수는 `{count,maxAllowed}`라 코어 `get_json`만 쓴다.
인터랙티브 OAuth가 아니므로 make_auth_client 없음(crossref/openalex와 동형).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.usgs_quake import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


def _user_agent() -> dict[str, str]:
    """식별용 User-Agent 헤더(무인증이라 인증 헤더는 없음)."""
    return {"User-Agent": "arcsolve/usgs_quake (https://github.com/ArcSolver/ArcSolve-Kit)"}


def _explain(e: UpstreamError) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    USGS는 에러 본문을 **text/plain**으로 준다(예: 400 `Error 400: Bad Request\n\nBad limit value
    "20001". Valid values are 0 <= limit <= 20000`). 비-dict(text) payload는 첫 의미 줄만 추려
    노출한다(장황한 Usage/Request 푸터는 자른다).
    출처: 라이브(/query?limit=20001 → 400 text/plain, /query?starttime=notadate → 400).
    """
    detail = ""
    if isinstance(e.payload, str) and e.payload.strip():
        # 'Error 400: Bad Request' 다음 첫 비어있지 않은 줄을 골라낸다.
        lines = [ln.strip() for ln in e.payload.splitlines() if ln.strip()]
        meaningful = [ln for ln in lines if not ln.lower().startswith("error ")]
        if meaningful:
            detail = f" {meaningful[0]}"
    if e.status == 400:
        return (
            "요청 오류(400): starttime/endtime(ISO8601)·magnitude·위치(latitude+longitude+"
            f"maxradiuskm)·limit(1–20000)·orderby를 확인하세요.{detail}"
        )
    if e.status in (204, 404):
        return "조건에 맞는 지진이 없습니다."
    if e.status == 414:
        return "요청 URL이 너무 깁니다(414): 조건을 줄이세요."
    if e.status == 429:
        return "요청 한도 초과(429): 잠시 후 재시도하세요."
    if e.status == 503:
        return "서비스 일시 불가(503): 잠시 후 재시도하세요."
    return f"USGS API 오류 {e.status}:{detail or ' ' + str(e.payload)}"


def _fmt_time(ms: int | None) -> str:
    """밀리초 epoch → UTC ISO8601 문자열. 없으면 '?'."""
    if ms is None:
        return "?"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coords(geom: c.FeatureGeometry | None) -> str:
    """geometry.coordinates[lon,lat,depth] → 'lat, lon (depth N km)' 사람용 표기. 없으면 '?'."""
    if not geom or not geom.coordinates or len(geom.coordinates) < 2:
        return "?"
    lon, lat = geom.coordinates[0], geom.coordinates[1]
    depth = geom.coordinates[2] if len(geom.coordinates) >= 3 else None
    base = f"{lat}, {lon}"
    return f"{base} (depth {depth} km)" if depth is not None else base


def _feature_line(f: c.Feature) -> str:
    """검색 결과 1줄: `- M{mag} {place} @ {time} [lat, lon (depth)] {url}`."""
    p = f.properties
    mag = p.mag if p and p.mag is not None else "?"
    place = (p.place if p and p.place else None) or "(위치 미상)"
    when = _fmt_time(p.time if p else None)
    where = _coords(f.geometry)
    url = (p.url if p and p.url else None) or "?"
    return f"- M{mag} {place} @ {when} [{where}] {url}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def usgs_search_earthquakes(
        starttime: str | None = None,
        endtime: str | None = None,
        minmagnitude: float | None = None,
        maxmagnitude: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        maxradiuskm: float | None = None,
        limit: int = c.DEFAULT_LIMIT,
        orderby: str | None = None,
    ) -> str:
        """USGS에서 지진 이벤트를 검색/나열한다(GET /query?format=geojson).

        Args:
            starttime: 시작 시각(ISO8601, 예: `2024-01-01` 또는 `2024-01-01T00:00:00`).
                미지정 시 상류 기본값(NOW-30일).
            endtime: 종료 시각(ISO8601). 미지정 시 현재.
            minmagnitude: 규모 하한(예: 4.5).
            maxmagnitude: 규모 상한.
            latitude: 원형 검색 중심 위도(-90..90). longitude·maxradiuskm와 함께 쓴다.
            longitude: 원형 검색 중심 경도(-180..180).
            maxradiuskm: 중심점 반경(km, 0..20001.6). latitude+longitude가 함께 필요.
            limit: 최대 결과 수. 기본 20, 1..20000.
            orderby: 정렬 `time`(기본·최신순)/`time-asc`/`magnitude`(큰 규모순)/`magnitude-asc`.
        """
        try:
            params = c.build_params(
                starttime=starttime, endtime=endtime,
                minmagnitude=minmagnitude, maxmagnitude=maxmagnitude,
                latitude=latitude, longitude=longitude, maxradiuskm=maxradiuskm,
                limit=limit, orderby=orderby,
            )
        except ValueError as e:  # limit/orderby/위치 범위 위반은 HTTP 전에 막힌다
            return str(e)

        try:
            body = await get_json(
                f"{c.BASE_URL}{c.QUERY}", params=params, headers=_user_agent()
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        fc = c.FeatureCollection.model_validate(body)
        if not fc.features:
            return "검색 결과 없음."
        note = f"{len(fc.features)}건"
        return note + "\n" + "\n".join(_feature_line(f) for f in fc.features)

    @mcp.tool
    async def usgs_count_earthquakes(
        starttime: str | None = None,
        endtime: str | None = None,
        minmagnitude: float | None = None,
        maxmagnitude: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        maxradiuskm: float | None = None,
    ) -> str:
        """조건에 매칭되는 지진 건수만 센다(GET /count?format=geojson).

        검색과 동일한 조건 파라미터를 받아 결과 본문 다운로드 없이 건수만 반환한다.
        응답: `{"count": N, "maxAllowed": 20000}`.

        Args:
            starttime: 시작 시각(ISO8601). 미지정 시 NOW-30일.
            endtime: 종료 시각(ISO8601). 미지정 시 현재.
            minmagnitude: 규모 하한.
            maxmagnitude: 규모 상한.
            latitude: 원형 검색 중심 위도(-90..90).
            longitude: 원형 검색 중심 경도(-180..180).
            maxradiuskm: 중심점 반경(km, 0..20001.6). latitude+longitude가 함께 필요.
        """
        try:
            params = c.build_params(
                starttime=starttime, endtime=endtime,
                minmagnitude=minmagnitude, maxmagnitude=maxmagnitude,
                latitude=latitude, longitude=longitude, maxradiuskm=maxradiuskm,
            )
        except ValueError as e:
            return str(e)

        try:
            body = await get_json(
                f"{c.BASE_URL}{c.COUNT}", params=params, headers=_user_agent()
            )
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        r = c.CountResult.model_validate(body)
        count = r.count if r.count is not None else "?"
        return f"조건 매칭 지진 {count}건"
