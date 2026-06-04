"""에어코리아 대기오염정보 읽기 MCP 도구 + 런타임 배선(자격증명·요청 조립·에러 매핑).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **서비스키 필수**(`AIRKOREA_SERVICE_KEY`) — OAuth가 아니라 **쿼리 파라미터
`serviceKey`**다(헤더 아님) → contract.build_*_params가 params에 넣는다. 사전발급 키이고
인터랙티브 OAuth가 아니므로 make_auth_client 없음(notion/openalex와 동형). 키가 없으면 HTTP
호출 전에 안내 문자열을 반환한다.

⚠️ data.go.kr 서비스키 함정: 키는 Encoding/Decoding 2종으로 발급된다. httpx가 쿼리 파라미터를
자동 URL-인코딩하므로 **Decoding 키(원문)**를 그대로 settings로 받아 넣는다(이중 인코딩 방지).

상류는 정상이어도 **HTTP 200**으로 응답하고, 키 오류 등은 봉투 `header.resultCode`(!= "00")로
온다. 그래서 _check_header로 봉투를 먼저 검사해 에러를 매핑한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.airkorea import contract as a

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class AirKoreaSettings(BaseSettings):
    """AIRKOREA_* 환경변수에서 자격증명을 로드한다.

    - service_key: data.go.kr 발급 서비스키(필수). **Decoding 키(원문)**를 넣는다
      (httpx 자동 인코딩으로 인한 이중 인코딩 방지).
    """

    model_config = SettingsConfigDict(env_prefix="AIRKOREA_", env_file=".env", extra="ignore")
    service_key: str | None = None


_MISSING_KEY = (
    "설정 오류: AIRKOREA_SERVICE_KEY가 없습니다. 공공데이터포털(data.go.kr)의 "
    "'대기오염정보' OpenAPI(ArpltnInforInqireSvc)를 신청해 서비스키를 발급받아 설정하세요. "
    "(발급: https://www.data.go.kr/data/15073861/openapi.do · "
    "⚠️ Encoding/Decoding 2종 중 **Decoding 키(원문)**를 넣으세요 — 이중 인코딩 방지.)"
)

# data.go.kr 공통 에러코드(서비스키/트래픽 등) → 사람이 읽을 안내.
# 출처: 공공데이터포털 OpenAPI 공통 에러코드 규약 + 응답 header.resultMsg.
_RESULT_CODE_HINTS = {
    "01": "어플리케이션 에러(01): 잠시 후 재시도하세요.",
    "02": "데이터베이스 에러(02): 잠시 후 재시도하세요.",
    "03": "데이터 없음(03): 해당 조건의 측정/예보 데이터가 없습니다.",
    "04": "HTTP 에러(04).",
    "12": "폐기된 서비스(12): 해당 OpenAPI는 더 이상 제공되지 않습니다.",
    "20": "서비스 접근 거부(20): 서비스키 권한/IP 설정을 확인하세요.",
    "22": "서비스 요청 제한 초과(22): 일일 트래픽 한도(개발계정 500/일)를 초과했습니다.",
    "30": (
        "등록되지 않은 서비스키(30): AIRKOREA_SERVICE_KEY를 확인하세요. "
        "⚠️ Encoding이 아니라 **Decoding 키(원문)**를 넣어야 합니다(이중 인코딩 방지)."
    ),
    "31": "기한 만료 서비스키(31): 활용기간이 만료되었습니다. data.go.kr에서 연장하세요.",
    "32": "등록되지 않은 IP(32): 서비스키에 허용 IP를 등록하세요.",
    "99": "기타 에러(99).",
}


def _explain(e: UpstreamError) -> str:
    """HTTP 4xx/5xx(드묾 — 보통 200+봉투 에러)를 사람이 읽을 메시지로 매핑한다.

    data.go.kr는 키 오류 등을 HTTP 200 + 봉투(_check_header)로 주는 일이 많지만, 게이트웨이
    레벨 차단은 4xx/5xx + 비-JSON(XML/HTML) 본문일 수 있다. dict가 아니면 원문 노출을 막는다.
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        # 봉투가 섞여올 수 있어 흔한 메시지 키를 훑는다.
        msg = payload.get("returnAuthMsg") or payload.get("resultMsg") or payload.get("message")
    detail = f" {msg}" if msg else ""  # 비-JSON(XML/HTML) 본문은 노출하지 않음
    if e.status in (401, 403):
        return (
            f"인증/권한 오류({e.status}): AIRKOREA_SERVICE_KEY(Decoding 키)와 서비스 권한을 "
            f"확인하세요.{detail}"
        )
    if e.status == 429:
        return f"요청 한도 초과(429): 일일 트래픽 한도를 확인하세요(개발계정 500/일).{detail}"
    return f"에어코리아 API 오류 {e.status}:{detail}"


def _check_header(header: a.Header | None) -> str | None:
    """봉투 header.resultCode를 검사한다. 정상("00")이면 None, 아니면 에러 안내 문자열.

    출처: https://www.data.go.kr/data/15073861/openapi.do (응답 header.resultCode/resultMsg).
    """
    if header is None or header.resultCode is None:
        return None  # header가 없으면 통과(데이터로 판단)
    code = header.resultCode
    if code == a.RESULT_CODE_OK:
        return None
    hint = _RESULT_CODE_HINTS.get(code)
    msg = header.resultMsg or ""
    if hint:
        return f"{hint}{(' (' + msg + ')') if msg else ''}"
    return f"에어코리아 응답 오류(resultCode={code}){(': ' + msg) if msg else ''}"


def _v(value: str | None) -> str:
    """측정값 문자열을 표시용으로 정규화한다(결측 '-'/None → '-')."""
    if value is None or value == "":
        return "-"
    return value


def _page_note(body: a.RealtimeBody | a.ForecastBody) -> str:
    """body 페이지네이션으로 '총 N건 · page P' 안내 문자열을 만든다."""
    total = body.totalCount if body.totalCount is not None else "?"
    note = f"총 {total}건"
    if body.pageNo is not None:
        note += f" · page {body.pageNo}"
    return note


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def airkorea_realtime_by_region(
        sidoName: str,  # noqa: N803 (공식 파라미터명)
        ver: str = a.DEFAULT_VER,
        numOfRows: int = a.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = a.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """시도별 실시간 측정정보를 조회한다(GET /getCtprvnRltmMesureDnsty).

        시도 단위로 측정소별 PM10/PM2.5/O3/NO2/CO/SO2와 통합대기환경지수(khai)를 돌려준다.
        측정값은 문자열이며 결측은 '-'.

        Args:
            sidoName: 시도명. 전국·서울·부산·대구·인천·광주·대전·울산·경기·강원·충북·충남·
                전북·전남·경북·경남·제주·세종 중 하나.
            ver: 응답 버전(필드 확장). 기본 1.3(PM2.5 포함). 1.4면 24시간 예측이동농도도.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = AirKoreaSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = a.build_realtime_by_region_params(
            sido_name=sidoName, service_key=s.service_key,
            ver=ver, num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            body = await get_json(f"{a.BASE_URL}{a.PATH_REALTIME_BY_REGION}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        resp = a.RealtimeResponse.model_validate(body.get("response", body))
        err = _check_header(resp.header)
        if err:
            return err
        if resp.body is None or not resp.body.items:
            return f"측정 데이터 없음. (시도={sidoName})"
        note = _page_note(resp.body)
        lines = [f"{note} · 시도 {sidoName}"]
        for m in resp.body.items:
            where = m.stationName or "(측정소?)"
            lines.append(
                f"- [{where}] {m.dataTime or '?'} · PM10 {_v(m.pm10Value)} · "
                f"PM2.5 {_v(m.pm25Value)} · O3 {_v(m.o3Value)} · NO2 {_v(m.no2Value)} · "
                f"CO {_v(m.coValue)} · SO2 {_v(m.so2Value)} · 통합 {_v(m.khaiValue)}"
            )
        return "\n".join(lines)

    @mcp.tool
    async def airkorea_realtime_by_station(
        stationName: str,  # noqa: N803 (공식 파라미터명)
        dataTerm: str = a.DEFAULT_DATA_TERM,  # noqa: N803
        ver: str = a.DEFAULT_VER,
        numOfRows: int = a.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = a.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """측정소별 실시간 측정정보를 조회한다(GET /getMsrstnAcctoRltmMesureDnsty).

        한 측정소의 시간대별 PM10/PM2.5/O3/NO2/CO/SO2·통합지수를 돌려준다.
        측정값은 문자열이며 결측은 '-'.

        Args:
            stationName: 측정소명(예: 종로구, 강남구). 측정소 목록은 별도 서비스에서 확인.
            dataTerm: 요청 기간. DAILY(기본)·MONTH·3MONTH 중 하나.
            ver: 응답 버전(필드 확장). 기본 1.3(PM2.5 포함).
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = AirKoreaSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = a.build_realtime_by_station_params(
            station_name=stationName, service_key=s.service_key,
            data_term=dataTerm, ver=ver, num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            body = await get_json(f"{a.BASE_URL}{a.PATH_REALTIME_BY_STATION}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        resp = a.RealtimeResponse.model_validate(body.get("response", body))
        err = _check_header(resp.header)
        if err:
            return err
        if resp.body is None or not resp.body.items:
            return f"측정 데이터 없음. (측정소={stationName})"
        note = _page_note(resp.body)
        lines = [f"{note} · 측정소 {stationName}"]
        for m in resp.body.items:
            lines.append(
                f"- {m.dataTime or '?'} · PM10 {_v(m.pm10Value)} · PM2.5 {_v(m.pm25Value)} · "
                f"O3 {_v(m.o3Value)} · NO2 {_v(m.no2Value)} · CO {_v(m.coValue)} · "
                f"SO2 {_v(m.so2Value)} · 통합 {_v(m.khaiValue)}"
            )
        return "\n".join(lines)

    @mcp.tool
    async def airkorea_forecast(
        searchDate: str,  # noqa: N803 (공식 파라미터명)
        informCode: str | None = None,  # noqa: N803
        numOfRows: int = a.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = a.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """대기질 예보통보를 조회한다(GET /getMinuDustFrcstDspth).

        발표일 기준으로 권역별 등급·개황·원인·행동요령을 돌려준다.

        Args:
            searchDate: 조회 발표일 `YYYY-MM-DD`.
            informCode: 오염물질 코드 필터(PM10·PM25·O3). 미지정 시 전체.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = AirKoreaSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = a.build_forecast_params(
            search_date=searchDate, service_key=s.service_key,
            inform_code=informCode, num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            body = await get_json(f"{a.BASE_URL}{a.PATH_FORECAST}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        resp = a.ForecastResponse.model_validate(body.get("response", body))
        err = _check_header(resp.header)
        if err:
            return err
        if resp.body is None or not resp.body.items:
            return f"예보 데이터 없음. (발표일={searchDate})"
        note = _page_note(resp.body)
        lines = [f"{note} · 발표일 {searchDate}"]
        for f in resp.body.items:
            lines.append(f"- [{f.informCode or '?'}] {f.informData or ''} ({f.dataTime or '?'} 발표)")
            if f.informOverall:
                lines.append(f"  개황: {f.informOverall}")
            if f.informGrade:
                lines.append(f"  등급: {f.informGrade}")
        return "\n".join(lines)
