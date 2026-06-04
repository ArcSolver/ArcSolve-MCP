"""서울 실시간 교통(지하철 도착 + 따릉이) 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **인증키 필수**(서울 열린데이터광장 발급) — OAuth가 아니라 **URL path의 첫 세그먼트**다
(쿼리/헤더 아님) → contract.build_*_url이 path에 박는다. 사전발급 키이고 인터랙티브 OAuth가
아니므로 make_auth_client 없음(airkorea/openalex와 동형). 키가 없으면 HTTP 호출 전에 안내를 반환.

⚠️ 인증키 2종 분리(핵심):
  - 지하철 실시간 도착: `SEOUL_SUBWAY_API_KEY`(별도 '실시간 지하철 인증키').
  - 따릉이: `SEOUL_OPENDATA_API_KEY`(표준 '일반 인증키').

상류는 키 오류·요청 오류·데이터 없음을 **HTTP 200 + 봉투**(RESULT.CODE / errorMessage.code)로
주는 일이 많아, 봉투를 먼저 검사해 에러를 매핑한다. 게이트웨이 레벨 차단은 4xx/5xx + 비-JSON일 수 있다.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.seoul_transit import contract as c

_KST = ZoneInfo("Asia/Seoul")  # recptnDt는 KST 기준 — 호스트 로컬타임과 무관하게 KST로 계산

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class SeoulTransitSettings(BaseSettings):
    """SEOUL_* 환경변수에서 인증키 2종을 로드한다.

    - subway_api_key: 지하철 실시간 도착 전용 '실시간 지하철 인증키'(env `SEOUL_SUBWAY_API_KEY`).
    - opendata_api_key: 따릉이 등 일반 데이터셋용 '일반 인증키'(env `SEOUL_OPENDATA_API_KEY`).
    인증키는 서울 열린데이터광장(data.seoul.go.kr)에서 발급한다.
    """

    model_config = SettingsConfigDict(env_prefix="SEOUL_", env_file=".env", extra="ignore")
    subway_api_key: str | None = None
    opendata_api_key: str | None = None


_MISSING_SUBWAY_KEY = (
    "설정 오류: SEOUL_SUBWAY_API_KEY가 없습니다. 지하철 실시간 도착은 **별도의 '실시간 지하철 "
    "인증키'**가 필요합니다(일반 인증키와 다름). 서울 열린데이터광장에서 신청해 설정하세요. "
    "(데이터셋: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do)"
)

_MISSING_OPENDATA_KEY = (
    "설정 오류: SEOUL_OPENDATA_API_KEY가 없습니다. 따릉이 등 일반 데이터셋은 서울 열린데이터광장 "
    "'일반 인증키'가 필요합니다. 신청해 설정하세요. "
    "(데이터셋: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do)"
)

# 서울 OpenAPI 공통 결과코드(RESULT.CODE / errorMessage.code) → 사람이 읽을 안내.
# 출처: 서울/자치구 열린데이터광장 공통 결과코드표
#   (https://data.gangnam.go.kr/openinf/openapiview.jsp?infId=OA-18724).
_CODE_HINTS = {
    "INFO-100": (
        "인증키 오류(INFO-100): 인증키가 유효하지 않습니다. "
        "해당 데이터셋용 인증키(지하철은 SEOUL_SUBWAY_API_KEY, 일반은 SEOUL_OPENDATA_API_KEY)를 확인하세요."
    ),
    "INFO-200": "데이터 없음(INFO-200): 해당하는 데이터가 없습니다.",
    "ERROR-300": "요청 오류(ERROR-300): 필수 값이 누락되었습니다.",
    "ERROR-301": "요청 오류(ERROR-301): 파일타입(요청 포맷) 값이 누락 혹은 유효하지 않습니다.",
    "ERROR-310": "서비스 없음(ERROR-310): 해당하는 서비스를 찾을 수 없습니다.",
    "ERROR-331": "요청 오류(ERROR-331): 요청 시작위치 값을 확인하세요.",
    "ERROR-332": "요청 오류(ERROR-332): 요청 종료위치 값을 확인하세요.",
    "ERROR-333": "요청 오류(ERROR-333): 요청위치 값의 타입이 유효하지 않습니다.",
    "ERROR-334": "요청 오류(ERROR-334): 요청 종료위치보다 시작위치가 더 큽니다.",
    "ERROR-336": "요청 범위 초과(ERROR-336): 1회 요청은 최대 1000건을 넘을 수 없습니다(end - start + 1 ≤ 1000).",
    "ERROR-500": "서버 오류(ERROR-500): 잠시 후 재시도하세요.",
    "ERROR-600": "DB 연결 오류(ERROR-600): 잠시 후 재시도하세요.",
    "ERROR-601": "DB 질의 오류(ERROR-601): 잠시 후 재시도하세요.",
}


def _explain_code(code: str | None, message: str | None) -> str | None:
    """봉투 결과코드를 검사한다. 정상(INFO-000)/없음이면 None, 아니면 에러 안내 문자열.

    출처: 서울 OpenAPI 공통 결과코드표.
    """
    if not code or code == c.RESULT_CODE_OK:
        return None
    hint = _CODE_HINTS.get(code)
    msg = (message or "").strip()
    if hint:
        return f"{hint}{(' (' + msg + ')') if msg else ''}"
    return f"서울 OpenAPI 응답 오류(code={code}){(': ' + msg) if msg else ''}"


def _explain_http(e: UpstreamError, *, what: str) -> str:
    """HTTP 4xx/5xx(게이트웨이 차단 등)를 사람이 읽을 메시지로 매핑한다.

    상류는 보통 HTTP 200 + 봉투로 에러를 주지만, 게이트웨이 레벨 차단은 4xx/5xx + 비-JSON
    (HTML/XML) 본문일 수 있다. dict가 아니면 원문 노출을 막는다.
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        msg = payload.get("message") or payload.get("MESSAGE")
    detail = f" {msg}" if msg else ""  # 비-JSON 본문은 노출하지 않음
    if e.status in (401, 403):
        return f"인증/권한 오류({e.status}): {what} 인증키를 확인하세요.{detail}"
    if e.status == 429:
        return f"요청 한도 초과(429): 잠시 후 재시도하세요.{detail}"
    return f"서울 교통 API 오류 {e.status}:{detail}"


def _v(value: str | None) -> str:
    """표시용 정규화(None/빈 문자열 → '-')."""
    if value is None or value == "":
        return "-"
    return value


def _age_note(recptn_dt: str | None) -> str:
    """recptnDt(생성 시각)와 현재 시각의 차를 'N초 전 생성' 보정 안내로 만든다.

    recptnDt는 `YYYY-MM-DD HH:MM:SS` 형식의 **과거 시각**(수집·가공 지연)이라, 실제 도착까지의
    시간은 이 시각 기준이다. 파싱 실패 시 원시각만 안내한다.
    출처: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do (recptnDt 주의사항).
    """
    if not recptn_dt:
        return ""
    try:
        gen = datetime.strptime(recptn_dt.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_KST)
    except (ValueError, TypeError):
        return f" (생성 {recptn_dt})"
    # KST-aware로 비교 — 호스트 타임존(UTC·미주·유럽 등)과 무관하게 정확한 경과시간.
    delta = int((datetime.now(_KST) - gen).total_seconds())
    if delta < 0:
        return f" (생성 {recptn_dt})"  # 시계 차이 등 — 음수면 원시각만
    return f" (생성 {recptn_dt} · {delta}초 전)"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def seoul_subway_arrivals(station_name: str) -> str:
        """서울 지하철 역의 실시간 도착정보를 조회한다(GET realtimeStationArrival).

        한 역(전 호선·상하행)의 다가오는 열차들을 돌려준다 — 도착 메시지("전역 출발" 등),
        현재 위치, 열차 종류, 종착역. 각 항목의 생성 시각(recptnDt)은 과거 시각이라
        '현재로부터 N초 전 생성'으로 보정해 함께 표시한다(실제 도착까지 시간은 이 시각 기준).

        ⚠️ 별도의 '실시간 지하철 인증키'(`SEOUL_SUBWAY_API_KEY`)가 필요하다(일반 인증키와 다름).

        Args:
            station_name: 지하철 역명(예: 강남, 서울, 시청). '역'은 붙이지 않는다.
        """
        s = SeoulTransitSettings()
        if not s.subway_api_key:
            return _MISSING_SUBWAY_KEY
        url = c.build_subway_url(station_name=station_name, api_key=s.subway_api_key)
        try:
            body = await get_json(url)
        except UpstreamError as e:
            return _explain_http(e, what="지하철(SEOUL_SUBWAY_API_KEY)")

        if not isinstance(body, dict):
            return f"응답: {body}"
        resp = c.SubwayResponse.model_validate(body)
        if resp.errorMessage is not None:
            err = _explain_code(resp.errorMessage.code, resp.errorMessage.message)
            if err:
                return err
        if not resp.realtimeArrivalList:
            return f"도착 정보 없음. (역={station_name})"
        total = resp.errorMessage.total if resp.errorMessage else None
        head = f"{station_name}역 실시간 도착"
        if total is not None:
            head += f" · 총 {total}건"
        lines = [head]
        for a in resp.realtimeArrivalList:
            line = a.trainLineNm or a.updnLine or "(방면?)"
            msg = a.arvlMsg2 or "-"
            here = f" · 현재 {a.arvlMsg3}" if a.arvlMsg3 else ""
            kind = f" · {a.btrainSttus}" if a.btrainSttus else ""
            dest = f" · {a.bstatnNm}행" if a.bstatnNm else ""
            lines.append(f"- [{line}] {msg}{here}{kind}{dest}{_age_note(a.recptnDt)}")
        return "\n".join(lines)

    @mcp.tool
    async def seoul_bike_status(
        start: int = c.BIKE_DEFAULT_START,
        end: int = c.BIKE_DEFAULT_END,
        station_name: str | None = None,
    ) -> str:
        """서울 따릉이 대여소의 실시간 현황을 조회한다(GET bikeList).

        대여소별 거치된 자전거 수(`parkingBikeTotCnt` = 대여 가능 수), 거치율(`shared`),
        위경도를 돌려준다. 1회 최대 1000건(end - start + 1 ≤ 1000) — 더 받으려면 start/end로
        페이지네이션한다. station_name을 주면 대여소명에 부분일치하는 항목만 추려서 보여준다
        (필터는 받아온 페이지 내에서만 적용된다).

        Args:
            start: 요청 시작 위치(1부터). 기본 1.
            end: 요청 종료 위치. 기본 1000. (end - start + 1 ≤ 1000)
            station_name: 대여소명 부분일치 필터(선택, 받아온 페이지 내에서 적용).
        """
        s = SeoulTransitSettings()
        if not s.opendata_api_key:
            return _MISSING_OPENDATA_KEY
        if end - start + 1 > c.BIKE_MAX_ROWS:
            return (
                f"요청 범위 초과: 1회 최대 {c.BIKE_MAX_ROWS}건입니다"
                f"(end - start + 1 ≤ {c.BIKE_MAX_ROWS}). 현재 {end - start + 1}건 요청."
            )
        url = c.build_bike_url(api_key=s.opendata_api_key, start=start, end=end)
        try:
            body = await get_json(url)
        except UpstreamError as e:
            return _explain_http(e, what="따릉이(SEOUL_OPENDATA_API_KEY)")

        if not isinstance(body, dict):
            return f"응답: {body}"
        resp = c.BikeResponse.model_validate(body)
        # 최상위 RESULT(서비스 래퍼 없이 온 인증키/요청 에러) 우선 검사.
        if resp.RESULT is not None:
            err = _explain_code(resp.RESULT.CODE, resp.RESULT.MESSAGE)
            if err:
                return err
        status = resp.rentBikeStatus
        if status is not None and status.RESULT is not None:
            err = _explain_code(status.RESULT.CODE, status.RESULT.MESSAGE)
            if err:
                return err
        rows = status.row if status else []
        if station_name:
            rows = [r for r in rows if r.stationName and station_name in r.stationName]
        if not rows:
            where = f" (필터='{station_name}')" if station_name else ""
            return f"따릉이 대여소 데이터 없음.{where}"
        total = status.list_total_count if status else None
        head = f"따릉이 대여소 {len(rows)}건"
        if total is not None:
            head += f" · 전체 {total}건"
        head += f" · 요청 {start}~{end}"
        lines = [head]
        for r in rows:
            name = r.stationName or "(대여소?)"
            rate = f" · 거치율 {r.shared}%" if r.shared else ""
            geo = ""
            if r.stationLatitude and r.stationLongitude:
                geo = f" · ({r.stationLatitude}, {r.stationLongitude})"
            lines.append(
                f"- [{name}] 자전거 {_v(r.parkingBikeTotCnt)}대 / 거치대 {_v(r.rackTotCnt)}{rate}{geo}"
            )
        return "\n".join(lines)
