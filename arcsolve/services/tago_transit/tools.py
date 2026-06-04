"""TAGO 전국 대중교통 통합 읽기 MCP 도구 + 런타임 배선(자격증명·요청 조립·에러 매핑).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **서비스키 필수**(`TAGO_SERVICE_KEY`) — OAuth가 아니라 **쿼리 파라미터 `serviceKey`**다
(헤더 아님) → contract.build_*_params가 params에 넣는다. 사전발급 키이고 인터랙티브 OAuth가
아니므로 make_auth_client 없음(airkorea/egen/openalex와 동형). 키가 없으면 HTTP 호출 전에
안내 문자열을 반환한다.

⚠️ data.go.kr 서비스키 함정: 키는 Encoding/Decoding 2종으로 발급된다. httpx가 쿼리 파라미터를
자동 URL-인코딩하므로 **Decoding 키(원문)**를 그대로 settings로 받아 넣는다(이중 인코딩 방지).

상류는 정상이어도 **HTTP 200**으로 응답하고, 키 오류·무데이터는 봉투 `header.resultCode`
(!= "00")로 온다. 게이트웨이 키 차단은 `<cmmMsgHeader><returnReasonCode>`(JSON에선
`cmmMsgHeader.returnReasonCode`)로 올 수 있다. 두 경로를 모두 검사한다.

⚠️ 코드 의존: 버스 도구는 cityCode(도시코드)+nodeId(정류소ID)/routeId가, 고속/시외는
터미널ID가, 열차는 역ID가 필요하다. `tago_city_codes`·`tago_search_bus_stops`가 버스 입력을
자기완결하게 보조한다. 터미널/역 ID 확보 경로는 README에 안내한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.tago_transit import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class TagoSettings(BaseSettings):
    """TAGO_* 환경변수에서 서비스키를 로드한다.

    - service_key: data.go.kr 발급 서비스키(필수). **Decoding 키(원문)**를 넣는다
      (httpx 자동 인코딩으로 인한 이중 인코딩 방지). 단일 키로 TAGO 6개 서비스 전부 커버한다.
    """

    model_config = SettingsConfigDict(env_prefix="TAGO_", env_file=".env", extra="ignore")
    service_key: str | None = None


_MISSING_KEY = (
    "설정 오류: TAGO_SERVICE_KEY가 없습니다. 공공데이터포털(data.go.kr)에서 국토교통부 TAGO "
    "대중교통 OpenAPI(버스도착/정류소/노선·고속/시외버스·열차 — 네임스페이스 1613000)를 활용 "
    "신청해 서비스키를 발급받아 설정하세요. 단일 키로 6개 서비스 전부 커버됩니다. "
    "(예: https://www.data.go.kr/data/15098530/openapi.do · "
    "⚠️ Encoding/Decoding 2종 중 **Decoding 키(원문)**를 넣으세요 — 이중 인코딩 방지.)"
)

# data.go.kr 공통 에러코드(서비스키/트래픽/무데이터 등) → 사람이 읽을 안내.
# 출처: 공공데이터포털 OpenAPI 공통 에러코드 규약 + 응답 header/cmmMsgHeader.
_RESULT_CODE_HINTS = {
    "01": "어플리케이션 에러(01): 잠시 후 재시도하세요.",
    "02": "데이터베이스 에러(02): 잠시 후 재시도하세요.",
    "03": "데이터 없음(03): 해당 조건의 운행/도착 데이터가 없습니다.",
    "04": "HTTP 에러(04).",
    "05": "서비스 연결 실패(05): 잠시 후 재시도하세요.",
    "10": "잘못된 요청 파라미터(10): 입력값(도시코드·ID·날짜)을 확인하세요.",
    "11": "필수 요청 파라미터 누락(11): cityCode/nodeId 등 필수값을 확인하세요.",
    "12": "폐기된 서비스(12): 해당 OpenAPI는 더 이상 제공되지 않습니다.",
    "20": "서비스 접근 거부(20): 서비스키 권한/IP 설정을 확인하세요.",
    "21": "일시적 사용 중지(21): 잠시 후 재시도하세요.",
    "22": "서비스 요청 제한 초과(22): 일일 트래픽 한도(개발계정)를 초과했습니다.",
    "30": (
        "등록되지 않은 서비스키(30): TAGO_SERVICE_KEY를 확인하세요. "
        "⚠️ Encoding이 아니라 **Decoding 키(원문)**를 넣어야 합니다(이중 인코딩 방지)."
    ),
    "31": "기한 만료 서비스키(31): 활용기간이 만료되었습니다. data.go.kr에서 연장하세요.",
    "32": "등록되지 않은 IP(32): 서비스키에 허용 IP를 등록하세요.",
    "99": "기타 에러(99).",
}


def _explain_http(e: UpstreamError) -> str:
    """HTTP 4xx/5xx(게이트웨이 차단 등)를 사람이 읽을 메시지로 매핑한다.

    TAGO는 키 오류 등을 HTTP 200 + 봉투로 주는 일이 많지만, 게이트웨이 레벨 차단은 4xx/5xx +
    비-JSON(XML/HTML) 본문일 수 있다. dict가 아니면 원문 노출을 막는다.
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
            f"인증/권한 오류({e.status}): TAGO_SERVICE_KEY(Decoding 키)와 서비스 권한을 "
            f"확인하세요.{detail}"
        )
    if e.status == 429:
        return f"요청 한도 초과(429): 일일 트래픽 한도를 확인하세요.{detail}"
    return f"TAGO API 오류 {e.status}:{detail}"


def _hint_for_code(code: str, msg: str) -> str:
    hint = _RESULT_CODE_HINTS.get(code)
    if hint:
        return f"{hint}{(' (' + msg + ')') if msg else ''}"
    return f"TAGO 응답 오류(resultCode={code}){(': ' + msg) if msg else ''}"


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

    @mcp.tool
    async def tago_city_codes() -> str:
        """전국 도시코드 목록을 조회한다(GET /ArvlInfoInqireService/getCtyCodeList).

        버스 도구(`tago_search_bus_stops`/`tago_bus_arrivals`/`tago_bus_route`)의 입력
        `city_code`를 얻기 위한 보조 도구. 각 도시명과 코드를 돌려준다.
        """
        s = TagoSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_city_code_params(service_key=s.service_key)
        url = f"{c.BASE_URL}{c.SERVICE_BUS_ARRIVAL}{c.OP_CITY_CODE}"
        res = await _fetch(url, params)
        if isinstance(res, str):
            return res
        _, resp = res
        rows = resp.body.item_dicts() if resp.body else []
        if not rows:
            return "도시코드 데이터 없음."
        codes = [c.CityCode.model_validate(r) for r in rows]
        lines = [f"도시코드 {len(codes)}건"]
        for cc in codes:
            lines.append(f"- {_v(cc.cityname)} = {_v(cc.citycode)}")
        return "\n".join(lines)

    @mcp.tool
    async def tago_search_bus_stops(
        city_code: str,
        node_name: str,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803 (공식 파라미터 의미)
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """정류소명으로 정류소를 검색한다(GET /BusSttnInfoInqireService/getSttnNoList).

        도시 내에서 이름으로 정류소를 찾아 **nodeId**(정류소ID)를 돌려준다 —
        `tago_bus_arrivals`의 입력 node_id를 얻는 보조 도구.

        Args:
            city_code: 도시코드(`tago_city_codes`로 조회).
            node_name: 정류소명(부분/전체).
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = TagoSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_station_search_params(
            city_code=city_code, node_name=node_name, service_key=s.service_key,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        url = f"{c.BASE_URL}{c.SERVICE_BUS_STATION}{c.OP_STATION_SEARCH}"
        res = await _fetch(url, params)
        if isinstance(res, str):
            return res
        _, resp = res
        rows = resp.body.item_dicts() if resp.body else []
        if not rows:
            return f"정류소 데이터 없음. (도시={city_code}, 이름='{node_name}')"
        stops = [c.BusStop.model_validate(r) for r in rows]
        lines = [f"{_page_note(resp.body)} · 정류소 검색 '{node_name}'"]
        for st in stops:
            no = f" (#{st.nodeno})" if st.nodeno else ""
            geo = ""
            if st.gpslati and st.gpslong:
                geo = f" · ({st.gpslati}, {st.gpslong})"
            lines.append(f"- [{_v(st.nodenm)}]{no} nodeId={_v(st.nodeid)}{geo}")
        return "\n".join(lines)

    @mcp.tool
    async def tago_bus_arrivals(
        city_code: str,
        node_id: str,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """정류소별 버스 실시간 도착예정을 조회한다(GET /ArvlInfoInqireService/…ArvlPrearngeInfoList).

        한 정류소(nodeId)에 곧 도착할 버스들을 노선번호·남은 정류장 수·도착예정시간(초)과 함께
        돌려준다. ⭐ 이 서비스의 핵심 도구.

        Args:
            city_code: 도시코드(`tago_city_codes`로 조회).
            node_id: 정류소ID(`tago_search_bus_stops`로 조회).
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = TagoSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_bus_arrival_params(
            city_code=city_code, node_id=node_id, service_key=s.service_key,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        url = f"{c.BASE_URL}{c.SERVICE_BUS_ARRIVAL}{c.OP_BUS_ARRIVAL}"
        res = await _fetch(url, params)
        if isinstance(res, str):
            return res
        _, resp = res
        rows = resp.body.item_dicts() if resp.body else []
        if not rows:
            return f"도착 예정 버스 없음. (도시={city_code}, nodeId={node_id})"
        arrivals = [c.BusArrival.model_validate(r) for r in rows]
        where = arrivals[0].nodenm or node_id
        lines = [f"{_page_note(resp.body)} · 정류소 {where} 실시간 도착"]
        for a in arrivals:
            mins = ""
            if a.arrtime and a.arrtime.isdigit():
                mins = f"(약 {int(a.arrtime) // 60}분)"
            lines.append(
                f"- [{_v(a.routeno)}] {_v(a.arrtime)}초 후 {mins} · "
                f"{_v(a.arrprevstationcnt)}정류장 전 · {_v(a.vehicletp)}"
            )
        return "\n".join(lines)

    @mcp.tool
    async def tago_bus_route(
        city_code: str,
        route_id: str,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """노선의 경유정류소 목록을 조회한다(GET /BusRouteInfoInqireService/…ThrghSttnList).

        한 노선(routeId)이 순서대로 지나는 정류소들을 돌려준다(경유 순번·상하행 포함).

        Args:
            city_code: 도시코드(`tago_city_codes`로 조회).
            route_id: 노선ID(도착예정 응답의 routeid 등에서 확보).
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = TagoSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_route_stations_params(
            city_code=city_code, route_id=route_id, service_key=s.service_key,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        url = f"{c.BASE_URL}{c.SERVICE_BUS_ROUTE}{c.OP_ROUTE_STATIONS}"
        res = await _fetch(url, params)
        if isinstance(res, str):
            return res
        _, resp = res
        rows = resp.body.item_dicts() if resp.body else []
        if not rows:
            return f"경유정류소 데이터 없음. (도시={city_code}, routeId={route_id})"
        stations = [c.RouteStation.model_validate(r) for r in rows]
        lines = [f"{_page_note(resp.body)} · 노선 {route_id} 경유정류소"]
        for st in stations:
            order = f"{st.nodeord}. " if st.nodeord else "- "
            updown = f" [{st.updowncd}]" if st.updowncd else ""
            lines.append(f"{order}{_v(st.nodenm)} (nodeId={_v(st.nodeid)}){updown}")
        return "\n".join(lines)

    async def _terminal_bus(
        *, service: str, op: str, label: str,
        dep_terminal_id: str, arr_terminal_id: str, dep_date: str,
        num_of_rows: int, page_no: int,
    ) -> str:
        """고속/시외 공통 핸들러(동형 파라미터·응답)."""
        s = TagoSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_terminal_bus_params(
            dep_terminal_id=dep_terminal_id, arr_terminal_id=arr_terminal_id,
            dep_date=dep_date, service_key=s.service_key,
            num_of_rows=num_of_rows, page_no=page_no,
        )
        url = f"{c.BASE_URL}{service}{op}"
        res = await _fetch(url, params)
        if isinstance(res, str):
            return res
        _, resp = res
        rows = resp.body.item_dicts() if resp.body else []
        if not rows:
            return (
                f"{label} 운행 데이터 없음. "
                f"(출발={dep_terminal_id}, 도착={arr_terminal_id}, 날짜={dep_date})"
            )
        buses = [c.TerminalBus.model_validate(r) for r in rows]
        lines = [f"{_page_note(resp.body)} · {label} {dep_terminal_id}→{arr_terminal_id} ({dep_date})"]
        for b in buses:
            grade = f"[{_v(b.gradeNm)}] " if b.gradeNm else ""
            fare = f" · {b.charge}원" if b.charge else ""
            route = f"{_v(b.depPlaceNm)}→{_v(b.arrPlaceNm)}"
            lines.append(
                f"- {grade}{_v(b.depPlandTime)} 출발 → {_v(b.arrPlandTime)} 도착 · {route}{fare}"
            )
        return "\n".join(lines)

    @mcp.tool
    async def tago_express_bus(
        dep_terminal_id: str,
        arr_terminal_id: str,
        dep_date: str,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """고속버스 운행을 조회한다(GET /ExpBusInfoService/getStrtpntAlocFndExpbusInfo).

        출발·도착 터미널ID와 날짜로 그날 운행하는 고속버스를 등급·요금·출/도착 시각과 함께
        돌려준다. ⚠️ 터미널ID는 고속버스 터미널 코드표에서 확보(README 참고).

        Args:
            dep_terminal_id: 출발 터미널ID(예: NAEK010).
            arr_terminal_id: 도착 터미널ID(예: NAEK300).
            dep_date: 출발일 `YYYYMMDD`.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        return await _terminal_bus(
            service=c.SERVICE_EXP_BUS, op=c.OP_EXP_BUS, label="고속버스",
            dep_terminal_id=dep_terminal_id, arr_terminal_id=arr_terminal_id,
            dep_date=dep_date, num_of_rows=numOfRows, page_no=pageNo,
        )

    @mcp.tool
    async def tago_intercity_bus(
        dep_terminal_id: str,
        arr_terminal_id: str,
        dep_date: str,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """시외버스 운행을 조회한다(GET /SuburbsBusInfoService/getStrtpntAlocFndSuberbsBusInfo).

        출발·도착 터미널ID와 날짜로 그날 운행하는 시외버스를 등급·요금·출/도착 시각과 함께
        돌려준다. ⚠️ 터미널ID는 시외버스 터미널 코드표에서 확보(README 참고).

        Args:
            dep_terminal_id: 출발 터미널ID.
            arr_terminal_id: 도착 터미널ID.
            dep_date: 출발일 `YYYYMMDD`.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        return await _terminal_bus(
            service=c.SERVICE_SUBURBS_BUS, op=c.OP_SUBURBS_BUS, label="시외버스",
            dep_terminal_id=dep_terminal_id, arr_terminal_id=arr_terminal_id,
            dep_date=dep_date, num_of_rows=numOfRows, page_no=pageNo,
        )

    @mcp.tool
    async def tago_train(
        dep_station_id: str,
        arr_station_id: str,
        dep_date: str,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """도시간 열차 운행을 조회한다(GET /TrainInfoService/getStrtpntAlocFndTrainInfo).

        출발·도착 역ID와 날짜로 그 구간 열차(KTX/일반 등)를 등급·열차번호·요금·출/도착 시각과
        함께 돌려준다. ⚠️ 역ID는 열차 역코드표에서 확보(README 참고).

        Args:
            dep_station_id: 출발 역ID(depPlaceId).
            arr_station_id: 도착 역ID(arrPlaceId).
            dep_date: 출발일 `YYYYMMDD`.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = TagoSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_train_params(
            dep_station_id=dep_station_id, arr_station_id=arr_station_id,
            dep_date=dep_date, service_key=s.service_key,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        url = f"{c.BASE_URL}{c.SERVICE_TRAIN}{c.OP_TRAIN}"
        res = await _fetch(url, params)
        if isinstance(res, str):
            return res
        _, resp = res
        rows = resp.body.item_dicts() if resp.body else []
        if not rows:
            return (
                f"열차 운행 데이터 없음. "
                f"(출발={dep_station_id}, 도착={arr_station_id}, 날짜={dep_date})"
            )
        trains = [c.Train.model_validate(r) for r in rows]
        lines = [
            f"{_page_note(resp.body)} · 열차 {dep_station_id}→{arr_station_id} ({dep_date})"
        ]
        for t in trains:
            grade = f"[{_v(t.traingradename)}] " if t.traingradename else ""
            no = f"#{t.trainno} " if t.trainno else ""
            fare = f" · {t.adultcharge}원" if t.adultcharge else ""
            route = f"{_v(t.depplacename)}→{_v(t.arrplacename)}"
            lines.append(
                f"- {grade}{no}{_v(t.depplandtime)} 출발 → {_v(t.arrplandtime)} 도착 · "
                f"{route}{fare}"
            )
        return "\n".join(lines)
