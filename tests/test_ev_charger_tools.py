"""EV Charger 도구 런타임 검증 — 네트워크 없이 요청 조립·XML 파싱·에러 매핑·키 누락 확인.

get_text는 raw str(XML)을 돌려주므로 RecordingHTTP의 ret도 str(XML)로 준다. 서비스키는 쿼리
파라미터로(헤더 아님) 들어가는지, 지역코드(zcode/zscode)·period가 조립되는지, 키가 원문 그대로
전달되는지(이중 인코딩 방지), stat 코드가 한글로 표시되는지, 봉투 resultCode 에러가 매핑되는지
확인한다. 키가 없으면 HTTP 호출 전에 안내를 반환해야 한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.ev_charger.tools import register

MOD = "arcsolve.services.ev_charger.tools"


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


STATUS_XML = _envelope(
    "<item>"
    "<busiId>ME</busiId><statId>28260005</statId><chgerId>02</chgerId>"
    "<stat>3</stat><statUpdDt>20190829121020</statUpdDt>"
    "</item>"
)

INFO_XML = _envelope(
    "<item>"
    "<statId>28260005</statId><statNm>환경공단 본사</statNm><chgerId>02</chgerId>"
    "<chgerType>04</chgerType><addr>인천광역시 서구 환경로 42</addr>"
    "<location>지하 1층 주차장</location><lat>37.5683</lat><lng>126.6517</lng>"
    "<useTime>24시간 이용가능</useTime><busiNm>한국환경공단</busiNm>"
    "<zcode>28</zcode><zscode>28260</zscode>"
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
    monkeypatch.setenv("EV_CHARGER_SERVICE_KEY", "DECODED_KEY")
    return load_tools(register)


# ─── 충전기 실시간 상태 ────────────────────────────────────


async def test_status_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=STATUS_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["evcharger_status"](zcode="11", zscode="11680")
    assert http.last["url"] == "http://apis.data.go.kr/B552584/EvCharger/getChargerStatus"
    # 서비스키는 쿼리 파라미터(헤더 아님), Decoding 키 원문 그대로(이중 인코딩 방지).
    assert http.last["params"]["serviceKey"] == "DECODED_KEY"
    assert http.last["params"]["zcode"] == "11"
    assert http.last["params"]["zscode"] == "11680"
    assert http.last["params"]["period"] == 5
    assert http.last.get("headers") is None
    assert "총 1건" in out and "page 1" in out
    # stat 코드는 한글로 표시.
    assert "충전중" in out and "3(충전중)" in out
    assert "20190829121020" in out
    # 5분 지연 안내가 출력에 명시되어야 한다.
    assert "5분" in out


async def test_status_omits_region_when_none(tools, monkeypatch, recording_http):
    http = recording_http(ret=STATUS_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"]()
    assert "zcode" not in http.last["params"]
    assert "zscode" not in http.last["params"]
    assert "전국" in out  # 지역 미지정 → 전국


async def test_status_missing_key_no_network(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("EV_CHARGER_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret=STATUS_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"](zcode="11")
    assert "EV_CHARGER_SERVICE_KEY" in out
    assert "Decoding" in out  # 이중 인코딩 함정 안내
    assert not http.calls  # HTTP 전에 막힘


async def test_status_empty_items(tools, monkeypatch, recording_http):
    http = recording_http(ret=_envelope("", total=0))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"](zcode="50")
    assert "데이터 없음" in out


async def test_status_period_clamped(tools, monkeypatch, recording_http):
    http = recording_http(ret=STATUS_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    await tools["evcharger_status"](period=99)
    assert http.last["params"]["period"] == 10  # 최대 10으로 클램프


# ─── 충전소 정보 ────────────────────────────────────────────


async def test_info_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=INFO_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["evcharger_info"](zcode="28")
    assert http.last["url"].endswith("/getChargerInfo")
    assert http.last["params"]["zcode"] == "28"
    assert "period" not in http.last["params"]  # period는 status 전용
    assert "환경공단 본사" in out
    # chgerType 코드는 한글로 표시.
    assert "04(DC콤보)" in out
    assert "인천광역시 서구 환경로 42" in out
    assert "(37.5683,126.6517)" in out  # 위경도
    assert "한국환경공단" in out
    assert "24시간 이용가능" in out


async def test_info_unknown_chger_type_preserves_code(tools, monkeypatch, recording_http):
    # 매핑에 없는 chgerType 코드는 원본 코드를 그대로 보존(환각 금지).
    xml = _envelope(
        "<item><statId>S1</statId><statNm>X충전소</statNm><chgerId>01</chgerId>"
        "<chgerType>99</chgerType></item>"
    )
    http = recording_http(ret=xml)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_info"](zcode="11")
    assert "타입 99" in out
    assert "99(" not in out  # 미상 코드엔 괄호 라벨 없음


# ─── resultCode 봉투 에러 매핑(HTTP 200) ───────────────────


async def test_result_code_30_unregistered_key(tools, monkeypatch, recording_http):
    # 봉투 <header>로 오는 resultCode=30.
    http = recording_http(
        ret=_envelope("", result_code="30", result_msg="SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    )
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"](zcode="11")
    assert "등록되지 않은 서비스키" in out
    assert "Decoding" in out  # 이중 인코딩 힌트


async def test_gateway_cmmmsgheader_error(tools, monkeypatch, recording_http):
    # 게이트웨이 차단은 <header> 없이 cmmMsgHeader로 온다(HTTP 200) — 30으로 매핑.
    http = recording_http(ret=GATEWAY_ERROR_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_info"](zcode="11")
    assert "등록되지 않은 서비스키" in out


async def test_result_code_22_traffic_limit(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_envelope("", result_code="22", result_msg="LIMITED_NUMBER_OF_SERVICE_REQUESTS")
    )
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"]()
    assert "요청 제한" in out


async def test_result_code_03_no_data(tools, monkeypatch, recording_http):
    http = recording_http(ret=_envelope("", result_code="03", result_msg="NODATA_ERROR"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_info"](zcode="99")
    assert "데이터 없음" in out


async def test_unknown_result_code(tools, monkeypatch, recording_http):
    http = recording_http(ret=_envelope("", result_code="77", result_msg="WEIRD"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"](zcode="11")
    assert "resultCode=77" in out and "WEIRD" in out


# ─── HTTP / 파싱 에러 매핑 ──────────────────────────────────


async def test_maps_http_401(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"returnAuthMsg": "SERVICE ACCESS DENIED"}))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"](zcode="11")
    assert "401" in out and "EV_CHARGER_SERVICE_KEY" in out


async def test_mapped_http_error_does_not_leak_non_dict_detail(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "<html><title>403 Forbidden</title></html>"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_info"](zcode="11")
    assert "403" in out
    assert "<html>" not in out and "<title>" not in out


async def test_unmapped_http_error_500(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(500, {"resultMsg": "INTERNAL"}))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"]()
    assert "500" in out


async def test_maps_xml_parse_error(tools, monkeypatch, recording_http):
    http = recording_http(ret="<response><body><items><item broken")
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["evcharger_status"](zcode="11")
    assert "파싱 실패" in out
