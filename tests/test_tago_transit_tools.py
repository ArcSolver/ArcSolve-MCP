"""TAGO Transit 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·키 누락 확인.

get_json은 본문 dict를 돌려준다(상류 봉투는 최상위 `{"response": {...}}`). 서비스키가 쿼리
파라미터로 들어가는지(헤더 아님), `_type=json`이 붙는지, 코드 의존 파라미터(cityCode/nodeId/
터미널ID/역ID)가 조립되는지, resultCode·cmmMsgHeader 봉투 에러가 매핑되는지, items quirk
(빈 문자열/단일 객체/배열)가 파싱되는지 확인한다. 키가 없으면 HTTP 전에 안내를 반환해야 한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.tago_transit.tools import register

MOD = "arcsolve.services.tago_transit.tools"


def _wrap(header, items=None, *, total=None, page=None):
    """상류 봉투 `{"response":{"header":..,"body":{"items":{"item":..}}}}`를 만든다."""
    resp = {"header": header}
    if items is not None or total is not None:
        body = {}
        if items is not None:
            body["items"] = {"item": items} if isinstance(items, list) else items
        if total is not None:
            body["totalCount"] = total
        if page is not None:
            body["pageNo"] = page
        resp["body"] = body
    return {"response": resp}


@pytest.fixture
def tools(monkeypatch, load_tools):
    """서비스키가 설정된 기본 환경."""
    monkeypatch.setenv("TAGO_SERVICE_KEY", "DECODED_KEY")
    return load_tools(register)


def test_all_seven_tools_registered(tools):
    assert set(tools) == {
        "tago_city_codes",
        "tago_search_bus_stops",
        "tago_bus_arrivals",
        "tago_bus_route",
        "tago_express_bus",
        "tago_intercity_bus",
        "tago_train",
    }


# ─── 도시코드 ───────────────────────────────────────────────


async def test_city_codes_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [{"citycode": 25, "cityname": "대전"}, {"citycode": 11, "cityname": "서울"}],
        total=2,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["tago_city_codes"]()
    assert http.last["url"] == (
        "http://apis.data.go.kr/1613000/ArvlInfoInqireService/getCtyCodeList"
    )
    # 서비스키는 쿼리 파라미터(헤더 아님), _type=json 명시.
    assert http.last["params"]["serviceKey"] == "DECODED_KEY"
    assert http.last["params"]["_type"] == "json"
    assert http.last.get("headers") is None
    assert "대전 = 25" in out and "서울 = 11" in out


# ─── 정류소 검색(코드 의존 보조) ────────────────────────────


async def test_search_bus_stops_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [{"nodeid": "DJB8001793", "nodenm": "시청", "nodeno": "40310", "gpslati": "36.3", "gpslong": "127.4"}],
        total=1, page=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["tago_search_bus_stops"](city_code="25", node_name="시청")
    assert http.last["url"].endswith("/BusSttnInfoInqireService/getSttnNoList")
    assert http.last["params"]["cityCode"] == "25"
    assert http.last["params"]["nodeNm"] == "시청"
    assert http.last["params"]["_type"] == "json"
    assert "nodeId=DJB8001793" in out
    assert "시청" in out and "(36.3, 127.4)" in out


# ─── 정류소 도착예정 ⭐ ─────────────────────────────────────


async def test_bus_arrivals_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [
            {
                "nodeid": "DJB8001793", "nodenm": "시청",
                "routeno": "100", "routetp": "간선버스",
                "arrprevstationcnt": "3", "vehicletp": "일반차량", "arrtime": "180",
            }
        ],
        total=1, page=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["tago_bus_arrivals"](city_code="25", node_id="DJB8001793")
    assert http.last["url"].endswith("/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList")
    # 코드 의존: cityCode + nodeId 둘 다 조립.
    assert http.last["params"]["cityCode"] == "25"
    assert http.last["params"]["nodeId"] == "DJB8001793"
    assert "정류소 시청 실시간 도착" in out
    assert "[100]" in out and "180초 후" in out
    assert "약 3분" in out  # 초→분 환산
    assert "3정류장 전" in out


async def test_bus_arrivals_single_item_object(tools, monkeypatch, recording_http):
    # data.go.kr quirk: 1건이면 item이 배열이 아닌 단일 객체.
    body = _wrap(
        {"resultCode": "00"},
        {"item": {"routeno": "7", "arrtime": "60", "arrprevstationcnt": "1", "vehicletp": "저상버스"}},
        total=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_bus_arrivals"](city_code="25", node_id="X")
    assert "[7]" in out and "60초 후" in out


async def test_bus_arrivals_empty_items_string(tools, monkeypatch, recording_http):
    # 무데이터: body.items가 빈 문자열.
    body = _wrap({"resultCode": "00"}, "", total=0)
    body["response"]["body"]["items"] = ""
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_bus_arrivals"](city_code="25", node_id="X")
    assert "도착 예정 버스 없음" in out


# ─── 노선 경유정류소 ────────────────────────────────────────


async def test_bus_route_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [
            {"nodeid": "A", "nodenm": "출발", "nodeord": "1", "updowncd": "0"},
            {"nodeid": "B", "nodenm": "도착", "nodeord": "2", "updowncd": "0"},
        ],
        total=2,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_bus_route"](city_code="25", route_id="DJB30300004")
    assert http.last["url"].endswith("/BusRouteInfoInqireService/getRouteAcctoThrghSttnList")
    assert http.last["params"]["routeId"] == "DJB30300004"
    assert "1. 출발" in out and "2. 도착" in out
    assert "nodeId=A" in out


# ─── 고속/시외버스(터미널ID) ────────────────────────────────


async def test_express_bus_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [
            {
                "gradeNm": "우등", "charge": "23000",
                "depPlandTime": "202401150900", "arrPlandTime": "202401151200",
                "depPlaceNm": "서울경부", "arrPlaceNm": "부산",
            }
        ],
        total=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_express_bus"](
        dep_terminal_id="NAEK010", arr_terminal_id="NAEK300", dep_date="20240115"
    )
    assert http.last["url"].endswith("/ExpBusInfoService/getStrtpntAlocFndExpbusInfo")
    assert http.last["params"]["depTerminalId"] == "NAEK010"
    assert http.last["params"]["arrTerminalId"] == "NAEK300"
    assert http.last["params"]["depPlandTime"] == "20240115"
    assert "[우등]" in out and "23000원" in out
    assert "서울경부→부산" in out


async def test_intercity_bus_uses_suburbs_service(tools, monkeypatch, recording_http):
    body = _wrap({"resultCode": "00"}, [{"gradeNm": "일반", "charge": "8000"}], total=1)
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_intercity_bus"](
        dep_terminal_id="T1", arr_terminal_id="T2", dep_date="20240115"
    )
    assert http.last["url"].endswith("/SuburbsBusInfoService/getStrtpntAlocFndSuberbsBusInfo")
    assert "시외버스" in out and "8000원" in out


# ─── 열차(역ID) ─────────────────────────────────────────────


async def test_train_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [
            {
                "traingradename": "KTX", "trainno": "101",
                "depplandtime": "20240115060000", "arrplandtime": "20240115080000",
                "depplacename": "서울", "arrplacename": "부산", "adultcharge": "59800",
            }
        ],
        total=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_train"](
        dep_station_id="NAT010000", arr_station_id="NAT013271", dep_date="20240115"
    )
    assert http.last["url"].endswith("/TrainInfoService/getStrtpntAlocFndTrainInfo")
    # 열차는 depPlaceId/arrPlaceId(역ID).
    assert http.last["params"]["depPlaceId"] == "NAT010000"
    assert http.last["params"]["arrPlaceId"] == "NAT013271"
    assert "[KTX]" in out and "#101" in out and "59800원" in out
    assert "서울→부산" in out


# ─── 키 누락(HTTP 전 차단) ──────────────────────────────────


async def test_missing_key_no_network(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("TAGO_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_bus_arrivals"](city_code="25", node_id="X")
    assert "TAGO_SERVICE_KEY" in out
    assert "Decoding" in out  # 이중 인코딩 함정 안내
    assert not http.calls  # HTTP 전에 막힘


async def test_missing_key_blocks_every_tool(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("TAGO_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    assert "TAGO_SERVICE_KEY" in await tools["tago_city_codes"]()
    assert "TAGO_SERVICE_KEY" in await tools["tago_search_bus_stops"](city_code="1", node_name="x")
    assert "TAGO_SERVICE_KEY" in await tools["tago_bus_route"](city_code="1", route_id="r")
    assert "TAGO_SERVICE_KEY" in await tools["tago_express_bus"](
        dep_terminal_id="a", arr_terminal_id="b", dep_date="20240115"
    )
    assert "TAGO_SERVICE_KEY" in await tools["tago_intercity_bus"](
        dep_terminal_id="a", arr_terminal_id="b", dep_date="20240115"
    )
    assert "TAGO_SERVICE_KEY" in await tools["tago_train"](
        dep_station_id="a", arr_station_id="b", dep_date="20240115"
    )
    assert not http.calls


# ─── resultCode 봉투 에러 매핑(HTTP 200) ───────────────────


async def test_result_code_30_unregistered_key(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_wrap({"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_bus_arrivals"](city_code="25", node_id="X")
    assert "등록되지 않은 서비스키" in out
    assert "Decoding" in out  # 이중 인코딩 힌트


async def test_result_code_22_traffic_limit(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_wrap({"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_train"](dep_station_id="a", arr_station_id="b", dep_date="20240115")
    assert "요청 제한" in out


async def test_result_code_03_no_data(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "03", "resultMsg": "NODATA_ERROR"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_express_bus"](
        dep_terminal_id="a", arr_terminal_id="b", dep_date="20240115"
    )
    assert "데이터 없음" in out


async def test_unknown_result_code(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "77", "resultMsg": "WEIRD"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_city_codes"]()
    assert "resultCode=77" in out and "WEIRD" in out


# ─── cmmMsgHeader(게이트웨이 키 차단) 보조 검사 ────────────


async def test_cmm_msg_header_gateway_block(tools, monkeypatch, recording_http):
    # header 없이 cmmMsgHeader로 키 차단이 오는 경우(returnReasonCode=30).
    http = recording_http(
        ret={
            "response": {
                "cmmMsgHeader": {
                    "returnReasonCode": "30",
                    "returnAuthMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
                }
            }
        }
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_bus_arrivals"](city_code="25", node_id="X")
    assert "등록되지 않은 서비스키" in out


async def test_openapi_service_response_wrapper_block(tools, monkeypatch, recording_http):
    # 게이트웨이가 OpenAPI_ServiceResponse로 한 번 더 감싸는 경우.
    http = recording_http(
        ret={
            "OpenAPI_ServiceResponse": {
                "cmmMsgHeader": {"returnReasonCode": "22", "returnAuthMsg": "LIMITED"}
            }
        }
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_train"](dep_station_id="a", arr_station_id="b", dep_date="20240115")
    assert "요청 제한" in out


# ─── HTTP 4xx/5xx 매핑(게이트웨이 차단 등) ─────────────────


async def test_maps_http_401(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"returnAuthMsg": "SERVICE ACCESS DENIED"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_bus_arrivals"](city_code="25", node_id="X")
    assert "401" in out and "TAGO_SERVICE_KEY" in out


async def test_http_error_does_not_leak_non_dict_detail(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "<html><title>403 Forbidden</title></html>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_city_codes"]()
    assert "403" in out
    assert "<html>" not in out and "<title>" not in out


async def test_unmapped_http_error_500(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(500, {"resultMsg": "INTERNAL"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["tago_intercity_bus"](
        dep_terminal_id="a", arr_terminal_id="b", dep_date="20240115"
    )
    assert "500" in out
