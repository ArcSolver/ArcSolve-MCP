"""E-Gen 도구 런타임 검증 — 네트워크 없이 요청 조립·XML 응답 파싱·에러 매핑·키 누락 확인.

get_text는 raw str(XML)을 돌려주므로 RecordingHTTP의 ret도 str(XML)로 준다. 서비스키는 쿼리
파라미터로(헤더 아님) 들어가는지, STAGE1/STAGE2가 조립되는지, 이중 인코딩 방지를 위해 키가
원문 그대로 전달되는지, 봉투 resultCode 에러가 매핑되는지 확인한다. 키가 없으면 HTTP 호출
전에 안내를 반환해야 한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.egen.tools import register

MOD = "arcsolve.services.egen.tools"


def _envelope(items_xml: str, result_code: str = "00", result_msg: str = "NORMAL SERVICE.",
              total: int = 1) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<response>"
        f"<header><resultCode>{result_code}</resultCode><resultMsg>{result_msg}</resultMsg></header>"
        f"<body><items>{items_xml}</items>"
        f"<numOfRows>100</numOfRows><pageNo>1</pageNo><totalCount>{total}</totalCount></body>"
        "</response>"
    )


REALTIME_XML = _envelope(
    "<item>"
    "<hpid>A1100001</hpid><dutyName>서울대학교병원</dutyName><dutyTel3>02-2072-0000</dutyTel3>"
    "<hvidate>20240115140000</hvidate>"
    "<hvec>12</hvec><hvoc>3</hvoc><hvicc>5</hvicc><hvgc>40</hvgc>"
    "<hvctayn>Y</hvctayn><hvmriayn>Y</hvmriayn><hvventiayn>N</hvventiayn><hvamyn>Y</hvamyn>"
    "</item>"
)

SEVERE_XML = _envelope(
    "<item>"
    "<hpid>A1100001</hpid><dutyName>서울대학교병원</dutyName><hvidate>20240115140000</hvidate>"
    "<MKioskTy1>Y</MKioskTy1><MKioskTy2>N</MKioskTy2><MKioskTy8>Y</MKioskTy8>"
    "</item>"
)

LIST_XML = _envelope(
    "<item>"
    "<rnum>1</rnum><hpid>A1100001</hpid><dutyName>서울대학교병원</dutyName>"
    "<dutyAddr>서울특별시 종로구 대학로 101</dutyAddr>"
    "<dutyTel1>02-2072-2114</dutyTel1><dutyTel3>02-2072-0000</dutyTel3>"
    "<dutyEmclsName>권역응급의료센터</dutyEmclsName>"
    "<wgs84Lon>126.999</wgs84Lon><wgs84Lat>37.579</wgs84Lat>"
    "</item>"
)

GATEWAY_ERROR_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<OpenAPI_ServiceResponse><cmmMsgHeader>"
    "<errMsg>SERVICE ERROR</errMsg>"
    "<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"
    "<returnReasonCode>30</returnReasonCode>"
    "</cmmMsgHeader></OpenAPI_ServiceResponse>"
)


@pytest.fixture
def tools(monkeypatch, load_tools):
    """서비스키가 설정된 기본 환경."""
    monkeypatch.setenv("EGEN_SERVICE_KEY", "DECODED_KEY")
    return load_tools(register)


# ─── 응급실 실시간 가용병상 ────────────────────────────────


async def test_realtime_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=REALTIME_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["egen_realtime_beds"](stage1="서울특별시", stage2="종로구")
    assert http.last["url"] == (
        "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
    )
    # 서비스키는 쿼리 파라미터(헤더 아님), Decoding 키 원문 그대로(이중 인코딩 방지).
    assert http.last["params"]["serviceKey"] == "DECODED_KEY"
    assert http.last["params"]["STAGE1"] == "서울특별시"
    assert http.last["params"]["STAGE2"] == "종로구"
    assert http.last.get("headers") is None
    assert "총 1건" in out and "page 1" in out
    assert "서울대학교병원" in out
    assert "응급실 12" in out and "수술실 3" in out
    assert "CT Y" in out and "인공호흡기 N" in out
    assert "02-2072-0000" in out


async def test_realtime_omits_stage2_when_none(tools, monkeypatch, recording_http):
    http = recording_http(ret=REALTIME_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    await tools["egen_realtime_beds"](stage1="서울특별시")
    assert "STAGE2" not in http.last["params"]
    assert http.last["params"]["STAGE1"] == "서울특별시"


async def test_realtime_missing_key_no_network(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("EGEN_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret=REALTIME_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_realtime_beds"](stage1="서울특별시")
    assert "EGEN_SERVICE_KEY" in out
    assert "Decoding" in out  # 이중 인코딩 함정 안내
    assert not http.calls  # HTTP 전에 막힘


async def test_realtime_empty_items(tools, monkeypatch, recording_http):
    http = recording_http(ret=_envelope("", total=0))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_realtime_beds"](stage1="제주특별자치도")
    assert "데이터 없음" in out


# ─── 중증질환자 수용가능 ───────────────────────────────────


async def test_severe_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=SEVERE_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["egen_severe_acceptance"](stage1="서울특별시")
    assert http.last["url"].endswith("/getSrsillDissAceptncPosblInfoInqire")
    assert "서울대학교병원" in out
    # 'Y'(수용 가능)인 MKioskTy 슬롯만 추려 표시, 'N'은 빠진다.
    assert "MKioskTy1" in out and "MKioskTy8" in out
    assert "MKioskTy2" not in out


async def test_severe_no_available_slots(tools, monkeypatch, recording_http):
    xml = _envelope(
        "<item><hpid>A1</hpid><dutyName>X병원</dutyName>"
        "<MKioskTy1>N</MKioskTy1></item>"
    )
    http = recording_http(ret=xml)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_severe_acceptance"](stage1="서울특별시")
    assert "정보없음" in out or "없음" in out


# ─── 응급의료기관 목록 ─────────────────────────────────────


async def test_list_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=LIST_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["egen_list"](stage1="서울특별시", stage2="종로구")
    assert http.last["url"].endswith("/getEgytListInfoInqire")
    assert http.last["params"]["STAGE2"] == "종로구"
    assert "서울대학교병원" in out
    assert "권역응급의료센터" in out
    assert "서울특별시 종로구 대학로 101" in out
    assert "02-2072-0000" in out  # dutyTel3 우선
    assert "(37.579,126.999)" in out  # 위경도


# ─── resultCode 봉투 에러 매핑(HTTP 200) ───────────────────


async def test_result_code_30_unregistered_key(tools, monkeypatch, recording_http):
    # 봉투 <header>로 오는 resultCode=30.
    http = recording_http(
        ret=_envelope("", result_code="30", result_msg="SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    )
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_realtime_beds"](stage1="서울특별시")
    assert "등록되지 않은 서비스키" in out
    assert "Decoding" in out  # 이중 인코딩 힌트


async def test_gateway_cmmmsgheader_error(tools, monkeypatch, recording_http):
    # 게이트웨이 차단은 <header> 없이 cmmMsgHeader로 온다(HTTP 200) — 30으로 매핑.
    http = recording_http(ret=GATEWAY_ERROR_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_list"](stage1="서울특별시")
    assert "등록되지 않은 서비스키" in out


async def test_result_code_22_traffic_limit(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_envelope("", result_code="22", result_msg="LIMITED_NUMBER_OF_SERVICE_REQUESTS")
    )
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_severe_acceptance"](stage1="서울특별시")
    assert "요청 제한" in out


async def test_result_code_03_no_data(tools, monkeypatch, recording_http):
    http = recording_http(ret=_envelope("", result_code="03", result_msg="NODATA_ERROR"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_list"](stage1="서울특별시")
    assert "데이터 없음" in out


async def test_unknown_result_code(tools, monkeypatch, recording_http):
    http = recording_http(ret=_envelope("", result_code="77", result_msg="WEIRD"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_realtime_beds"](stage1="서울특별시")
    assert "resultCode=77" in out and "WEIRD" in out


async def test_canonical_codes_now_mapped(tools, monkeypatch, recording_http):
    # 감사: 이 서비스가 누락했던 게이트웨이 코드(05/10/11/21)가 이제 canonical 안내로 매핑된다.
    for code, needle in (
        ("05", "연결 실패"),
        ("10", "잘못된 요청 파라미터"),
        ("11", "필수 요청 파라미터"),
        ("21", "일시적"),
    ):
        http = recording_http(ret=_envelope("", result_code=code, result_msg="X"))
        monkeypatch.setattr(f"{MOD}.get_text", http)
        out = await tools["egen_realtime_beds"](stage1="서울특별시")
        assert needle in out, code
        assert "resultCode=" not in out, code


# ─── HTTP / 파싱 에러 매핑 ──────────────────────────────────


async def test_maps_http_401(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"returnAuthMsg": "SERVICE ACCESS DENIED"}))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_realtime_beds"](stage1="서울특별시")
    assert "401" in out and "EGEN_SERVICE_KEY" in out


async def test_mapped_http_error_does_not_leak_non_dict_detail(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "<html><title>403 Forbidden</title></html>"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_list"](stage1="서울특별시")
    assert "403" in out
    assert "<html>" not in out and "<title>" not in out


async def test_unmapped_http_error_500(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(500, {"resultMsg": "INTERNAL"}))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_severe_acceptance"](stage1="서울특별시")
    assert "500" in out


async def test_maps_xml_parse_error(tools, monkeypatch, recording_http):
    http = recording_http(ret="<response><body><items><item broken")
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["egen_realtime_beds"](stage1="서울특별시")
    assert "파싱 실패" in out
