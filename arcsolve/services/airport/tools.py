"""인천국제공항 여객편 운항현황 읽기 MCP 도구 + 런타임 배선(자격증명·요청 조립·에러 매핑).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **서비스키 필수**(`AIRPORT_SERVICE_KEY`) — OAuth가 아니라 **쿼리 파라미터 `serviceKey`**다
(헤더 아님) → contract.build_flight_params가 params에 넣는다. 사전발급 키이고 인터랙티브 OAuth가
아니므로 make_auth_client 없음(airkorea/egen/tago와 동형). 키가 없으면 HTTP 호출 전에 안내
문자열을 반환한다.

⚠️ data.go.kr 서비스키 함정: 키는 Encoding/Decoding 2종으로 발급된다. httpx가 쿼리 파라미터를
자동 URL-인코딩하므로 **Decoding 키(원문)**를 그대로 settings로 받아 넣는다(이중 인코딩 방지).

⚠️ 개발계정 **일 500건** 트래픽 제한(운영계정은 활용사례 등록 후 상향) — README 명시.

상류는 정상이어도 **HTTP 200**으로 응답하고, 키 오류·무데이터는 봉투 `header.resultCode`
(!= "00")로 온다. 게이트웨이 키 차단은 `<cmmMsgHeader><returnReasonCode>`(JSON에선
`cmmMsgHeader.returnReasonCode`)로 올 수 있다. 두 경로를 모두 검사한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.airport import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class AirportSettings(BaseSettings):
    """AIRPORT_* 환경변수에서 서비스키를 로드한다.

    - service_key: data.go.kr 발급 서비스키(필수). **Decoding 키(원문)**를 넣는다
      (httpx 자동 인코딩으로 인한 이중 인코딩 방지). 인천국제공항공사 항공기 운항현황 상세조회
      (15140153) 활용신청으로 발급. ⚠️ 개발계정 일 500건 제한.
    """

    model_config = SettingsConfigDict(env_prefix="AIRPORT_", env_file=".env", extra="ignore")
    service_key: str | None = None


_MISSING_KEY = (
    "설정 오류: AIRPORT_SERVICE_KEY가 없습니다. 공공데이터포털(data.go.kr)에서 인천국제공항공사 "
    "'항공기 운항 현황 상세 조회'(여객편 운항현황 — 데이터 15140153)를 활용 신청해 서비스키를 "
    "발급받아 설정하세요. (https://www.data.go.kr/data/15140153/openapi.do · "
    "⚠️ Encoding/Decoding 2종 중 **Decoding 키(원문)**를 넣으세요 — 이중 인코딩 방지. "
    "개발계정은 일 500건 트래픽 제한이 있습니다.)"
)

# data.go.kr 공통 에러코드(서비스키/트래픽/무데이터 등) → 사람이 읽을 안내.
# 출처: 공공데이터포털 OpenAPI 공통 에러코드 규약 + 응답 header/cmmMsgHeader.
_RESULT_CODE_HINTS = {
    "01": "어플리케이션 에러(01): 잠시 후 재시도하세요.",
    "02": "데이터베이스 에러(02): 잠시 후 재시도하세요.",
    "03": "데이터 없음(03): 해당 조건의 운항 데이터가 없습니다.",
    "04": "HTTP 에러(04).",
    "05": "서비스 연결 실패(05): 잠시 후 재시도하세요.",
    "10": "잘못된 요청 파라미터(10): 입력값(날짜·시간·공항코드)을 확인하세요.",
    "11": "필수 요청 파라미터 누락(11): 필수값을 확인하세요.",
    "12": "폐기된 서비스(12): 해당 OpenAPI는 더 이상 제공되지 않습니다.",
    "20": "서비스 접근 거부(20): 서비스키 권한/IP 설정을 확인하세요.",
    "21": "일시적 사용 중지(21): 잠시 후 재시도하세요.",
    "22": (
        "서비스 요청 제한 초과(22): 일일 트래픽 한도를 초과했습니다. "
        "(개발계정은 일 500건 제한 — 운영계정 전환 시 상향 가능)"
    ),
    "30": (
        "등록되지 않은 서비스키(30): AIRPORT_SERVICE_KEY를 확인하세요. "
        "⚠️ Encoding이 아니라 **Decoding 키(원문)**를 넣어야 합니다(이중 인코딩 방지)."
    ),
    "31": "기한 만료 서비스키(31): 활용기간이 만료되었습니다. data.go.kr에서 연장하세요.",
    "32": "등록되지 않은 IP(32): 서비스키에 허용 IP를 등록하세요.",
    "99": "기타 에러(99).",
}


def _explain_http(e: UpstreamError) -> str:
    """HTTP 4xx/5xx(게이트웨이 차단 등)를 사람이 읽을 메시지로 매핑한다.

    인천공항 API는 키 오류 등을 HTTP 200 + 봉투로 주는 일이 많지만, 게이트웨이 레벨 차단은
    4xx/5xx + 비-JSON(XML/HTML) 본문일 수 있다. dict가 아니면 원문 노출을 막는다.
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        msg = (
            payload.get("returnAuthMsg")
            or payload.get("resultMsg")
            or payload.get("returnReasonCode")
            or payload.get("message")
        )
    detail = f" {msg}" if msg else ""  # 비-JSON(XML/HTML) 본문은 노출하지 않음
    if e.status in (401, 403):
        return (
            f"인증/권한 오류({e.status}): AIRPORT_SERVICE_KEY(Decoding 키)와 서비스 권한을 "
            f"확인하세요.{detail}"
        )
    if e.status == 429:
        return f"요청 한도 초과(429): 일일 트래픽 한도(개발계정 일 500건)를 확인하세요.{detail}"
    return f"인천공항 API 오류 {e.status}:{detail}"


def _hint_for_code(code: str, msg: str) -> str:
    hint = _RESULT_CODE_HINTS.get(code)
    if hint:
        return f"{hint}{(' (' + msg + ')') if msg else ''}"
    return f"인천공항 응답 오류(resultCode={code}){(': ' + msg) if msg else ''}"


def _check_envelope(body: dict, resp: c.Response) -> str | None:
    """봉투를 검사한다. 정상("00")/없음이면 None, 아니면 에러 안내 문자열.

    1) `response.header.resultCode` 우선 검사.
    2) 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`(+ returnAuthMsg)로 올 수 있어 보조 검사.
    출처: data.go.kr 응답 header/cmmMsgHeader 규약.
    """
    header = resp.header
    if header is not None and header.resultCode is not None:
        if header.resultCode != c.RESULT_CODE_OK:
            return _hint_for_code(header.resultCode, header.resultMsg or "")
        return None
    # header가 없을 때만 cmmMsgHeader(게이트웨이 차단) 보조 검사.
    cmm = body.get("cmmMsgHeader") if isinstance(body, dict) else None
    if not isinstance(cmm, dict):
        # OpenAPI 게이트웨이가 OpenAPI_ServiceResponse로 한 번 더 감싸는 경우.
        wrapper = body.get("OpenAPI_ServiceResponse") if isinstance(body, dict) else None
        if isinstance(wrapper, dict):
            cmm = wrapper.get("cmmMsgHeader")
    if isinstance(cmm, dict):
        code = cmm.get("returnReasonCode")
        amsg = cmm.get("returnAuthMsg") or cmm.get("errMsg") or ""
        if code is not None and str(code) not in ("", c.RESULT_CODE_OK):
            return _hint_for_code(str(code), str(amsg))
    return None


def _unwrap_response(body: Any) -> dict | None:
    """상류 본문에서 `response` 봉투를 꺼낸다(없으면 본문 그대로 시도)."""
    if not isinstance(body, dict):
        return None
    inner = body.get("response")
    return inner if isinstance(inner, dict) else body


def _v(value: str | None) -> str:
    """표시용 정규화(None/빈 문자열/'-' → '-')."""
    if value is None or value == "":
        return "-"
    return value


def _fmt_time(dt: str | None) -> str:
    """YYYYMMDDHHMM(또는 HHMM 등)을 표시용 HH:MM으로 정규화한다(파싱 실패 시 원문)."""
    if not dt:
        return "-"
    digits = dt.strip()
    if len(digits) >= 12 and digits[:12].isdigit():
        return f"{digits[8:10]}:{digits[10:12]}"
    if len(digits) == 4 and digits.isdigit():
        return f"{digits[:2]}:{digits[2:]}"
    return dt


def _fmt_terminal(tid: str | None) -> str:
    """terminalid 코드(P01/P02/P03)를 표시 접미사로 환산한다.

    상류는 표시명이 아니라 코드를 준다(P01=T1·P02=탑승동·P03=T2). 매핑에 없으면 코드 원문을
    그대로 보여준다(미래 코드 방어). 결측이면 빈 문자열. 출처: contract.TERMINAL_NAMES.
    """
    if not tid:
        return ""
    name = c.TERMINAL_NAMES.get(tid, tid)
    return f" · {name}"


def _page_note(b: c.Body | None) -> str:
    """body 페이지네이션으로 '총 N건 · page P' 안내 문자열을 만든다."""
    if b is None:
        return ""
    total = b.totalCount if b.totalCount is not None else "?"
    note = f"총 {total}건"
    if b.pageNo is not None:
        note += f" · page {b.pageNo}"
    return note


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    async def _fetch(url: str, params: dict) -> tuple[dict, c.Response] | str:
        """공통: GET → 봉투 파싱 + 에러 매핑. 에러면 안내 문자열, 정상이면 (raw, Response)."""
        try:
            body = await get_json(url, params=params)
        except UpstreamError as e:
            return _explain_http(e)
        if not isinstance(body, dict):
            return f"응답: {body}"
        inner = _unwrap_response(body)
        resp = c.Response.model_validate(inner if inner is not None else {})
        err = _check_envelope(inner if inner is not None else body, resp)
        if err:
            return err
        return body, resp

    async def _flights(
        *,
        op: str,
        direction: str,
        search_day: str | None,
        from_time: str,
        to_time: str,
        airport_code: str | None,
        flight_id: str | None,
        lang: str,
        num_of_rows: int,
        page_no: int,
    ) -> str:
        """도착/출발 공통 핸들러(동형 파라미터·응답)."""
        s = AirportSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_flight_params(
            service_key=s.service_key,
            search_day=search_day,
            from_time=from_time,
            to_time=to_time,
            airport_code=airport_code,
            flight_id=flight_id,
            lang=lang,
            num_of_rows=num_of_rows,
            page_no=page_no,
        )
        url = f"{c.BASE_URL}{c.SERVICE_PASSENGER_FLIGHTS}{op}"
        res = await _fetch(url, params)
        if isinstance(res, str):
            return res
        _, resp = res
        rows = resp.body.item_dicts() if resp.body else []
        when = search_day or "당일"
        if not rows:
            filt = f", 공항={airport_code}" if airport_code else ""
            filt += f", 편명={flight_id}" if flight_id else ""
            return f"{direction} 운항 데이터 없음. (날짜={when}, {from_time}~{to_time}{filt})"
        flights = [c.PassengerFlight.model_validate(r) for r in rows]
        head = f"{_page_note(resp.body)} · 인천공항 여객편 {direction} ({when} {from_time}~{to_time})"
        lines = [head]
        for f in flights:
            sched = _fmt_time(f.scheduleDateTime)
            est = _fmt_time(f.estimatedDateTime)
            time_part = sched if est in ("-", sched) else f"{sched}→{est}"
            place = _v(f.airport)
            if f.airportCode:
                place += f"({f.airportCode})"
            terminal = _fmt_terminal(f.terminalid)
            status = f" [{f.remark}]" if f.remark else ""
            # 공동운항(codeshare)이고 주 편명이 따로 있으면 부기.
            share = ""
            if f.masterflightid and f.masterflightid not in ("", "-"):
                share = f" (공동운항·주 {f.masterflightid})"
            # 방향별 부가 정보.
            if direction == "도착":
                extra = ""
                if f.carousel and f.carousel not in ("", "-"):
                    extra += f" · 수취대 {f.carousel}"
                if f.exitnumber and f.exitnumber not in ("", "-"):
                    extra += f" · 출구 {f.exitnumber}"
            else:
                extra = ""
                if f.chkinrange and f.chkinrange not in ("", "-"):
                    extra += f" · 카운터 {f.chkinrange}"
                if f.gatenumber and f.gatenumber not in ("", "-"):
                    extra += f" · 탑승구 {f.gatenumber}"
            lines.append(
                f"- {_v(f.flightId)}{share} {_v(f.airline)} · {place} · "
                f"{time_part}{terminal}{extra}{status}"
            )
        return "\n".join(lines)

    @mcp.tool
    async def airport_arrivals(
        search_day: str | None = None,
        from_time: str = c.DEFAULT_FROM_TIME,
        to_time: str = c.DEFAULT_TO_TIME,
        airport_code: str | None = None,
        flight_id: str | None = None,
        lang: str = c.LANG_KOREAN,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803 (공식 파라미터 의미)
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """인천공항 여객편 도착현황을 조회한다(GET /StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp).

        편명·항공사·출발지·예정/변경시각·터미널·수하물수취대·출구·운항상태를 돌려준다. ⭐ 핵심 도구.

        Args:
            search_day: 조회일자 `YYYYMMDD`(미지정 시 상류 기본=당일). 조회 가능 범위는 D-3~D+6.
            from_time: 조회 시작시각 `HHMM`(기본 0000).
            to_time: 조회 종료시각 `HHMM`(기본 2400).
            airport_code: 출발지 공항코드(IATA, 선택 필터 — 예: NRT).
            flight_id: 편명 필터(선택 — 예: KE001).
            lang: 언어 K(국문)/E(영문)(기본 K).
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        return await _flights(
            op=c.OP_ARRIVALS, direction="도착",
            search_day=search_day, from_time=from_time, to_time=to_time,
            airport_code=airport_code, flight_id=flight_id, lang=lang,
            num_of_rows=numOfRows, page_no=pageNo,
        )

    @mcp.tool
    async def airport_departures(
        search_day: str | None = None,
        from_time: str = c.DEFAULT_FROM_TIME,
        to_time: str = c.DEFAULT_TO_TIME,
        airport_code: str | None = None,
        flight_id: str | None = None,
        lang: str = c.LANG_KOREAN,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """인천공항 여객편 출발현황을 조회한다(GET /StatusOfPassengerFlightsDeOdp/getPassengerDeparturesDeOdp).

        편명·항공사·목적지·예정/변경시각·터미널·체크인카운터·탑승구·운항상태를 돌려준다. ⭐ 핵심 도구.

        Args:
            search_day: 조회일자 `YYYYMMDD`(미지정 시 상류 기본=당일). 조회 가능 범위는 D-3~D+6.
            from_time: 조회 시작시각 `HHMM`(기본 0000).
            to_time: 조회 종료시각 `HHMM`(기본 2400).
            airport_code: 목적지 공항코드(IATA, 선택 필터 — 예: NRT).
            flight_id: 편명 필터(선택 — 예: KE001).
            lang: 언어 K(국문)/E(영문)(기본 K).
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        return await _flights(
            op=c.OP_DEPARTURES, direction="출발",
            search_day=search_day, from_time=from_time, to_time=to_time,
            airport_code=airport_code, flight_id=flight_id, lang=lang,
            num_of_rows=numOfRows, page_no=pageNo,
        )
