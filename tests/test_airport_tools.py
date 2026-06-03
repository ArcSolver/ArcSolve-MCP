"""Airport(인천공항 운항현황) 도구 런타임 검증 — 네트워크 없이 요청 조립·파싱·에러 매핑·키 누락.

get_json은 본문 dict를 돌려준다(상류 봉투는 최상위 `{"response": {...}}`). 서비스키가 쿼리
파라미터로 들어가는지(헤더 아님), `type=json`(인천공항은 `_type` 아님)이 붙는지, 시간범위·
선택 필터가 조립되는지, resultCode·cmmMsgHeader 봉투 에러가 매핑되는지, items quirk
(직접 리스트/단일 객체/빈 문자열)가 파싱되는지 확인한다. 키가 없으면 HTTP 전에 안내를 반환해야 한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.airport.tools import register

MOD = "arcsolve.services.airport.tools"


def _wrap(header, items=None, *, total=None, page=None):
    """상류 봉투 `{"response":{"header":..,"body":{"items":[...]}}}`를 만든다.

    인천공항은 body.items가 곧장 리스트다(item 중첩 없음).
    """
    resp = {"header": header}
    if items is not None or total is not None:
        body = {}
        if items is not None:
            body["items"] = items
        if total is not None:
            body["totalCount"] = total
        if page is not None:
            body["pageNo"] = page
        resp["body"] = body
    return {"response": resp}


@pytest.fixture
def tools(monkeypatch, load_tools):
    """서비스키가 설정된 기본 환경."""
    monkeypatch.setenv("AIRPORT_SERVICE_KEY", "DECODED_KEY")
    return load_tools(register)


def test_both_tools_registered(tools):
    assert set(tools) == {"airport_arrivals", "airport_departures"}


# ─── 도착 ⭐ ────────────────────────────────────────────────


async def test_arrivals_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [
            {
                "airline": "대한항공", "flightId": "KE001",
                "airport": "나리타", "airportCode": "NRT",
                "scheduleDateTime": "202401151230", "estimatedDateTime": "202401151245",
                "terminalid": "2", "carousel": "7", "exitnumber": "A", "remark": "도착",
            }
        ],
        total=1, page=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["airport_arrivals"]()
    assert http.last["url"] == (
        "http://apis.data.go.kr/B551177/StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp"
    )
    # 서비스키는 쿼리 파라미터(헤더 아님), type=json(인천공항은 _type 아님).
    assert http.last["params"]["serviceKey"] == "DECODED_KEY"
    assert http.last["params"]["type"] == "json"
    assert "_type" not in http.last["params"]
    assert http.last["params"]["from_time"] == "0000"
    assert http.last["params"]["to_time"] == "2400"
    assert http.last["params"]["lang"] == "K"
    assert http.last.get("headers") is None
    # 출력: 편명·항공사·출발지·시각·터미널·수취대·출구·상태.
    assert "KE001" in out and "대한항공" in out
    assert "나리타(NRT)" in out
    assert "12:30→12:45" in out  # 예정→변경 시각 환산
    assert "T2" in out
    assert "수취대 7" in out and "출구 A" in out
    assert "[도착]" in out


async def test_arrivals_filters_assembled(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "00"}, [], total=0))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["airport_arrivals"](
        search_day="20240115", from_time="0600", to_time="1200",
        airport_code="NRT", flight_id="KE001", lang="E",
    )
    assert http.last["params"]["searchday"] == "20240115"
    assert http.last["params"]["from_time"] == "0600"
    assert http.last["params"]["to_time"] == "1200"
    assert http.last["params"]["airport_code"] == "NRT"
    assert http.last["params"]["flight_id"] == "KE001"
    assert http.last["params"]["lang"] == "E"


async def test_arrivals_single_item_object(tools, monkeypatch, recording_http):
    # 인천공항 quirk: 1건이면 items가 곧장 단일 객체.
    body = _wrap(
        {"resultCode": "00"},
        {"airline": "제주항공", "flightId": "7C101", "scheduleDateTime": "202401150900"},
        total=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"]()
    assert "7C101" in out and "제주항공" in out and "09:00" in out


async def test_arrivals_empty_items_string(tools, monkeypatch, recording_http):
    body = _wrap({"resultCode": "00"}, "", total=0)
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"](search_day="20240115")
    assert "도착 운항 데이터 없음" in out
    assert "20240115" in out


# ─── 출발 ⭐ ────────────────────────────────────────────────


async def test_departures_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        [
            {
                "airline": "아시아나", "flightId": "OZ102",
                "airport": "로스앤젤레스", "airportCode": "LAX",
                "scheduleDateTime": "202401151400",
                "terminalid": "1", "chkinrange": "A~C", "gatenumber": "24", "remark": "탑승중",
            }
        ],
        total=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["airport_departures"]()
    assert http.last["url"].endswith(
        "/StatusOfPassengerFlightsDeOdp/getPassengerDeparturesDeOdp"
    )
    assert http.last["params"]["type"] == "json"
    # 출력: 편명·항공사·목적지·터미널·체크인카운터·탑승구·상태.
    assert "OZ102" in out and "아시아나" in out
    assert "로스앤젤레스(LAX)" in out
    assert "T1" in out
    assert "카운터 A~C" in out and "탑승구 24" in out
    assert "[탑승중]" in out


# ─── 키 누락(HTTP 전 차단) ──────────────────────────────────


async def test_missing_key_no_network(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("AIRPORT_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"]()
    assert "AIRPORT_SERVICE_KEY" in out
    assert "Decoding" in out  # 이중 인코딩 함정 안내
    assert "500" in out  # 일 500건 제한 안내
    assert not http.calls  # HTTP 전에 막힘


async def test_missing_key_blocks_both_tools(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("AIRPORT_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    assert "AIRPORT_SERVICE_KEY" in await tools["airport_arrivals"]()
    assert "AIRPORT_SERVICE_KEY" in await tools["airport_departures"]()
    assert not http.calls


# ─── resultCode 봉투 에러 매핑(HTTP 200) ───────────────────


async def test_result_code_30_unregistered_key(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_wrap({"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"]()
    assert "등록되지 않은 서비스키" in out
    assert "Decoding" in out  # 이중 인코딩 힌트


async def test_result_code_22_traffic_limit_mentions_500(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_wrap({"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_departures"]()
    assert "요청 제한" in out
    assert "500" in out  # 개발계정 일 500건 안내


async def test_result_code_03_no_data(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "03", "resultMsg": "NODATA_ERROR"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"]()
    assert "데이터 없음" in out


async def test_unknown_result_code(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "77", "resultMsg": "WEIRD"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"]()
    assert "resultCode=77" in out and "WEIRD" in out


# ─── cmmMsgHeader(게이트웨이 키 차단) 보조 검사 ────────────


async def test_cmm_msg_header_gateway_block(tools, monkeypatch, recording_http):
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
    out = await tools["airport_arrivals"]()
    assert "등록되지 않은 서비스키" in out


async def test_openapi_service_response_wrapper_block(tools, monkeypatch, recording_http):
    http = recording_http(
        ret={
            "OpenAPI_ServiceResponse": {
                "cmmMsgHeader": {"returnReasonCode": "22", "returnAuthMsg": "LIMITED"}
            }
        }
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_departures"]()
    assert "요청 제한" in out


# ─── HTTP 4xx/5xx 매핑(게이트웨이 차단 등) ─────────────────


async def test_maps_http_401(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"returnAuthMsg": "SERVICE ACCESS DENIED"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"]()
    assert "401" in out and "AIRPORT_SERVICE_KEY" in out


async def test_http_error_does_not_leak_non_dict_detail(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "<html><title>403 Forbidden</title></html>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_departures"]()
    assert "403" in out
    assert "<html>" not in out and "<title>" not in out


async def test_unmapped_http_error_500(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(500, {"resultMsg": "INTERNAL"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airport_arrivals"]()
    assert "500" in out
