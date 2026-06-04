"""Parking 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·키 누락 확인.

get_json은 본문 dict를 돌려준다(B553881 봉투는 최상위에 resultCode + 오퍼레이션명 키 아래 항목).
서비스키가 쿼리 파라미터로 들어가는지(헤더 아님), `format=2`가 붙는지, 오퍼레이션 경로가 맞는지,
resultCode·cmmMsgHeader 봉투 에러가 매핑되는지, items quirk(단일 객체/배열/누락)가 파싱되는지,
실시간 잔여면 0/누락이 올바로 표시되는지 확인한다. 키가 없으면 HTTP 전에 안내를 반환해야 한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.parking.tools import register

MOD = "arcsolve.services.parking.tools"


def _env(op, items=None, *, code="00", msg="SUCCESS", total=None, page=None):
    """B553881 봉투 `{resultCode,..,<op>: [...]}`를 만든다(항목은 op 키 아래)."""
    body = {"resultCode": code, "resultMsg": msg}
    if total is not None:
        body["totalCount"] = total
    if page is not None:
        body["pageNo"] = page
    if items is not None:
        body[op] = items
    return body


@pytest.fixture
def tools(monkeypatch, load_tools):
    """서비스키가 설정된 기본 환경."""
    monkeypatch.setenv("PARKING_SERVICE_KEY", "DECODED_KEY")
    return load_tools(register)


def test_all_three_tools_registered(tools):
    assert set(tools) == {"parking_search", "parking_operation", "parking_realtime"}


# ─── 시설정보 ───────────────────────────────────────────────


async def test_search_request_and_output(tools, monkeypatch, recording_http):
    body = _env(
        "PrkSttusInfo",
        [
            {
                "prk_center_id": "12345-67890-12345-12-1",
                "prk_plce_nm": "망원동 주차장",
                "prk_plce_adres": "서울시 망원동 월드컵로 1길",
                "prk_plce_entrc_la": "35.879337",
                "prk_plce_entrc_lo": "128.628764",
                "prk_cmprt_co": "100",
            }
        ],
        total=1,
        page=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["parking_search"]()
    assert http.last["url"] == "https://apis.data.go.kr/B553881/Parking/PrkSttusInfo"
    # 서비스키는 쿼리 파라미터(헤더 아님), format=2 명시.
    assert http.last["params"]["serviceKey"] == "DECODED_KEY"
    assert http.last["params"]["format"] == "2"
    assert http.last.get("headers") is None
    assert "망원동 주차장" in out
    assert "PK=12345-67890-12345-12-1" in out
    assert "총 100면" in out
    assert "(35.879337, 128.628764)" in out


async def test_search_single_object_quirk(tools, monkeypatch, recording_http):
    # 1건이면 오퍼레이션명 값이 배열이 아닌 단일 객체.
    body = _env("PrkSttusInfo", {"prk_center_id": "A", "prk_plce_nm": "단건"}, total=1)
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_search"]()
    assert "단건" in out and "PK=A" in out


async def test_search_empty(tools, monkeypatch, recording_http):
    body = _env("PrkSttusInfo", None, total=0)  # 오퍼레이션 키 없음(0건).
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_search"]()
    assert "시설정보 없음" in out


# ─── 운영정보 ───────────────────────────────────────────────


async def test_operation_request_and_output(tools, monkeypatch, recording_http):
    body = _env(
        "PrkOprInfo",
        [
            {
                "prk_center_id": "PK1",
                "opertn_start_time": "080000",
                "opertn_end_time": "200000",
                "opertn_bs_free_time": "30",
                "parking_chrge_bs_time": "30",
                "parking_chrge_bs_chrg": "1500",
                "parking_chrge_adit_unit_time": "30",
                "parking_chrge_adit_unit_chrge": "1000",
            }
        ],
        total=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_operation"]()
    assert http.last["url"].endswith("/PrkOprInfo")
    assert "PK=PK1" in out
    assert "운영 080000~200000" in out
    assert "기본 30분 1500원" in out
    assert "추가 30분당 1000원" in out
    assert "무료회차 30분" in out


async def test_operation_empty_notes_coverage(tools, monkeypatch, recording_http):
    body = _env("PrkOprInfo", None, total=0)
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_operation"]()
    assert "운영정보 없음" in out and "연동 주차장 한정" in out


# ─── 실시간 잔여면 ⭐ ───────────────────────────────────────


async def test_realtime_request_and_output(tools, monkeypatch, recording_http):
    body = _env(
        "PrkRealtimeInfo",
        [
            {
                "prk_center_id": "PK1",
                "pkfc_ParkingLots_total": "140",
                "pkfc_Available_ParkingLots_total": "42",
            }
        ],
        total=1,
        page=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_realtime"]()
    assert http.last["url"].endswith("/PrkRealtimeInfo")
    assert http.last["params"]["format"] == "2"
    assert "PK=PK1" in out
    assert "잔여 42/140면" in out
    # 커버리지 한계가 출력 헤더에 명시돼야 한다.
    assert "연동 주차장 한정" in out


async def test_realtime_zero_available_preserved(tools, monkeypatch, recording_http):
    # 잔여 0면도 "-"가 아니라 "0"으로 표시돼야 한다(만차).
    body = _env(
        "PrkRealtimeInfo",
        {"prk_center_id": "PK1", "pkfc_ParkingLots_total": "50", "pkfc_Available_ParkingLots_total": 0},
        total=1,
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_realtime"]()
    assert "잔여 0/50면" in out


async def test_realtime_empty_notes_coverage_limit(tools, monkeypatch, recording_http):
    # 실시간 무데이터는 정상일 수 있음(연동 주차장 한정) — 안내 명시.
    body = _env("PrkRealtimeInfo", None, total=0)
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_realtime"]()
    assert "실시간 잔여면" in out and "연동된 일부 주차장만" in out


# ─── 키 누락(HTTP 전 차단) ──────────────────────────────────


async def test_missing_key_no_network(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("PARKING_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_realtime"]()
    assert "PARKING_SERVICE_KEY" in out
    assert "Decoding" in out  # 이중 인코딩 함정 안내
    assert not http.calls  # HTTP 전에 막힘


async def test_missing_key_blocks_every_tool(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("PARKING_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    assert "PARKING_SERVICE_KEY" in await tools["parking_search"]()
    assert "PARKING_SERVICE_KEY" in await tools["parking_operation"]()
    assert "PARKING_SERVICE_KEY" in await tools["parking_realtime"]()
    assert not http.calls


# ─── resultCode 봉투 에러 매핑(HTTP 200) ───────────────────


async def test_result_code_30_unregistered_key(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_env("PrkSttusInfo", code="30", msg="SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_search"]()
    assert "등록되지 않은 서비스키" in out
    assert "Decoding" in out  # 이중 인코딩 힌트


async def test_result_code_22_traffic_limit(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_env("PrkRealtimeInfo", code="22", msg="LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_realtime"]()
    assert "요청 제한" in out


async def test_result_code_03_no_data(tools, monkeypatch, recording_http):
    http = recording_http(ret=_env("PrkOprInfo", code="03", msg="NODATA_ERROR"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_operation"]()
    assert "데이터 없음" in out


async def test_unknown_result_code(tools, monkeypatch, recording_http):
    http = recording_http(ret=_env("PrkSttusInfo", code="77", msg="WEIRD"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_search"]()
    assert "resultCode=77" in out and "WEIRD" in out


# ─── cmmMsgHeader(게이트웨이 키 차단) 보조 검사 ────────────


async def test_cmm_msg_header_gateway_block(tools, monkeypatch, recording_http):
    # resultCode 없이 cmmMsgHeader로 키 차단이 오는 경우(returnReasonCode=30).
    http = recording_http(
        ret={
            "cmmMsgHeader": {
                "returnReasonCode": "30",
                "returnAuthMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
            }
        }
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_search"]()
    assert "등록되지 않은 서비스키" in out


async def test_openapi_service_response_wrapper_block(tools, monkeypatch, recording_http):
    # 게이트웨이가 OpenAPI_ServiceResponse로 감싸는 경우.
    http = recording_http(
        ret={
            "OpenAPI_ServiceResponse": {
                "cmmMsgHeader": {"returnReasonCode": "22", "returnAuthMsg": "LIMITED"}
            }
        }
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_realtime"]()
    assert "요청 제한" in out


# ─── HTTP 4xx/5xx 매핑(게이트웨이 차단 등) ─────────────────


async def test_maps_http_401(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"returnAuthMsg": "SERVICE ACCESS DENIED"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_search"]()
    assert "401" in out and "PARKING_SERVICE_KEY" in out


async def test_http_error_does_not_leak_non_dict_detail(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "<html><title>403 Forbidden</title></html>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_realtime"]()
    assert "403" in out
    assert "<html>" not in out and "<title>" not in out


async def test_unmapped_http_error_500(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(500, {"resultMsg": "INTERNAL"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["parking_operation"]()
    assert "500" in out
