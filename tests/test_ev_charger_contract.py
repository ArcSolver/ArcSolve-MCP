"""EV Charger 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·코드표(stat/chgerType)·쿼리 빌더(serviceKey Decoding 원문·지역코드 생략·
numOfRows/period 클램프·페이지네이션)·XML 봉투/항목 파싱(문자열 값·결측·게이트웨이
cmmMsgHeader 에러). HTTP 없음.
"""

import xml.etree.ElementTree as ET

from arcsolve.services.ev_charger.contract import (
    BASE_URL,
    CHGER_TYPE_LABELS,
    DEFAULT_NUM_OF_ROWS,
    DEFAULT_PAGE_NO,
    DEFAULT_PERIOD,
    MAX_NUM_OF_ROWS,
    MAX_PERIOD,
    MIN_NUM_OF_ROWS,
    MIN_PERIOD,
    PATH_CHARGER_INFO,
    PATH_CHARGER_STATUS,
    RESULT_CODE_OK,
    STAT_LABELS,
    Charger,
    ChargerStatus,
    Header,
    build_charger_info_params,
    build_charger_status_params,
    parse_charger_info,
    parse_charger_status,
    parse_header,
)


# ─── 상수 / 코드표 ──────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://apis.data.go.kr/B552584/EvCharger"
    assert PATH_CHARGER_INFO == "/getChargerInfo"
    assert PATH_CHARGER_STATUS == "/getChargerStatus"
    assert RESULT_CODE_OK == "00"
    assert DEFAULT_NUM_OF_ROWS == 100
    assert DEFAULT_PAGE_NO == 1
    assert (MIN_NUM_OF_ROWS, MAX_NUM_OF_ROWS) == (10, 9999)
    assert DEFAULT_PERIOD == 5
    assert (MIN_PERIOD, MAX_PERIOD) == (1, 10)


def test_stat_labels_match_official():
    # 출처: data.go.kr getChargerStatus 응답 stat 설명.
    assert STAT_LABELS["1"] == "통신이상"
    assert STAT_LABELS["2"] == "충전대기"
    assert STAT_LABELS["3"] == "충전중"
    assert STAT_LABELS["4"] == "운영중지"
    assert STAT_LABELS["5"] == "점검중"
    assert STAT_LABELS["9"] == "상태미확인"


def test_chger_type_labels_have_combo_and_slow():
    # DC콤보(04)·AC완속(02)은 가이드/표준데이터 통용값.
    assert CHGER_TYPE_LABELS["04"] == "DC콤보"
    assert CHGER_TYPE_LABELS["02"] == "AC완속"


def test_chger_type_labels_recent_codes_cross_verified():
    # 09=NACS·10=DC콤보+NACS는 다수 외부 구현 교차확인값(heeaayoon·EJGo-712·seung-2001·EVeryCharge).
    # 과거 오기(10=DC차데모+DC콤보는 실은 05번 코드)를 방지하는 회귀 가드.
    assert CHGER_TYPE_LABELS["08"] == "DC콤보(완속)"
    assert CHGER_TYPE_LABELS["09"] == "NACS"
    assert CHGER_TYPE_LABELS["10"] == "DC콤보+NACS"
    assert CHGER_TYPE_LABELS["05"] == "DC차데모+DC콤보"  # 05와 10이 섞이지 않도록


# ─── 쿼리 빌더 ──────────────────────────────────────────────


def test_build_status_includes_key_and_period():
    p = build_charger_status_params(service_key="DECODED")
    # 서비스키는 쿼리 파라미터(헤더 아님) — Decoding 키 원문(httpx 자동 인코딩에 맡김).
    assert p["serviceKey"] == "DECODED"
    assert p["pageNo"] == 1
    assert p["numOfRows"] == 100
    assert p["period"] == 5
    # 지역코드 미지정이면 키 자체가 빠진다(전국).
    assert "zcode" not in p and "zscode" not in p


def test_build_status_includes_region_codes_when_given():
    p = build_charger_status_params(
        service_key="K", zcode="11", zscode="11680", period=3, num_of_rows=50, page_no=2
    )
    assert p["zcode"] == "11"
    assert p["zscode"] == "11680"
    assert p["period"] == 3
    assert p["numOfRows"] == 50
    assert p["pageNo"] == 2


def test_build_info_omits_period_and_region():
    p = build_charger_info_params(service_key="K")
    assert p["serviceKey"] == "K"
    assert "period" not in p  # period는 status 전용
    assert "zcode" not in p and "zscode" not in p


def test_build_info_includes_zcode_only():
    p = build_charger_info_params(service_key="K", zcode="26")
    assert p["zcode"] == "26"
    assert "zscode" not in p


def test_numofrows_clamped_to_official_bounds():
    # 상류 제약 [10, 9999]로 클램프.
    lo = build_charger_status_params(service_key="K", num_of_rows=1)
    hi = build_charger_info_params(service_key="K", num_of_rows=100000)
    assert lo["numOfRows"] == 10
    assert hi["numOfRows"] == 9999


def test_period_clamped_to_official_bounds():
    lo = build_charger_status_params(service_key="K", period=0)
    hi = build_charger_status_params(service_key="K", period=99)
    assert lo["period"] == 1
    assert hi["period"] == 10


def test_empty_region_codes_are_omitted():
    # 빈 문자열도 생략(falsy) — 전국으로 동작.
    p = build_charger_info_params(service_key="K", zcode="", zscode="")
    assert "zcode" not in p and "zscode" not in p


# ─── 응답 모델 / XML 파싱 ──────────────────────────────────

STATUS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item>
        <busiId>ME</busiId>
        <statId>28260005</statId>
        <chgerId>02</chgerId>
        <stat>3</stat>
        <statUpdDt>20190829121020</statUpdDt>
      </item>
      <item>
        <busiId>ME</busiId>
        <statId>28260005</statId>
        <chgerId>03</chgerId>
        <stat>2</stat>
      </item>
    </items>
    <numOfRows>100</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>2</totalCount>
  </body>
</response>"""

INFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item>
        <statId>28260005</statId>
        <statNm>환경공단 본사</statNm>
        <chgerId>02</chgerId>
        <chgerType>04</chgerType>
        <addr>인천광역시 서구 환경로 42</addr>
        <location>지하 1층 주차장</location>
        <lat>37.5683</lat>
        <lng>126.6517</lng>
        <useTime>24시간 이용가능</useTime>
        <busiNm>한국환경공단</busiNm>
        <zcode>28</zcode>
        <zscode>28260</zscode>
      </item>
    </items>
    <numOfRows>100</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>1</totalCount>
  </body>
</response>"""

# 게이트웨이(서비스키) 차단 — <header> 없이 cmmMsgHeader로 온다.
GATEWAY_ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OpenAPI_ServiceResponse>
  <cmmMsgHeader>
    <errMsg>SERVICE ERROR</errMsg>
    <returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>
    <returnReasonCode>30</returnReasonCode>
  </cmmMsgHeader>
</OpenAPI_ServiceResponse>"""


def test_header_model():
    h = Header.model_validate({"resultCode": "00", "resultMsg": "NORMAL SERVICE.", "x": "ign"})
    assert h.resultCode == "00"
    assert h.resultMsg == "NORMAL SERVICE."


def test_status_values_are_strings_and_missing_blank():
    # 상태/식별 필드는 문자열, 결측은 캐스팅하지 않는다.
    st = ChargerStatus.model_validate(
        {"statId": "28260005", "chgerId": "02", "stat": "3", "unexpected": "ign"}
    )
    assert st.stat == "3"
    assert st.chgerId == "02"
    assert st.statUpdDt is None


def test_charger_model_geo_and_type_strings():
    ch = Charger.model_validate(
        {"statId": "S1", "chgerType": "04", "lat": "37.5", "lng": "127.0", "parkingFree": "Y"}
    )
    assert ch.chgerType == "04"
    assert ch.lat == "37.5" and ch.lng == "127.0"
    assert ch.parkingFree == "Y"


def test_parse_charger_status_envelope_and_page():
    header, items, page = parse_charger_status(STATUS_XML)
    assert header.resultCode == "00"
    assert page == (2, 1, 100)  # totalCount, pageNo, numOfRows
    assert len(items) == 2
    assert items[0].stat == "3"
    assert items[0].statUpdDt == "20190829121020"
    assert items[1].stat == "2"
    assert items[1].statUpdDt is None  # 결측은 None(빈 요소 없음)


def test_parse_charger_info_fields():
    header, items, page = parse_charger_info(INFO_XML)
    assert header.resultCode == "00"
    assert page == (1, 1, 100)
    assert len(items) == 1
    ch = items[0]
    assert ch.statNm == "환경공단 본사"
    assert ch.chgerType == "04"
    assert ch.addr == "인천광역시 서구 환경로 42"
    assert ch.lat == "37.5683" and ch.lng == "126.6517"
    assert ch.useTime == "24시간 이용가능"
    assert ch.busiNm == "한국환경공단"
    assert ch.zcode == "28" and ch.zscode == "28260"


def test_parse_header_falls_back_to_cmmmsgheader():
    # 게이트웨이 키 오류는 <header> 없이 cmmMsgHeader로 온다 — resultCode/resultMsg를 채운다.
    root = ET.fromstring(GATEWAY_ERROR_XML)
    h = parse_header(root)
    assert h.resultCode == "30"
    assert "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in (h.resultMsg or "")


def test_parse_empty_items():
    xml = (
        "<response><header><resultCode>03</resultCode><resultMsg>NODATA</resultMsg></header>"
        "<body><items></items><totalCount>0</totalCount></body></response>"
    )
    header, items, page = parse_charger_status(xml)
    assert header.resultCode == "03"
    assert items == []
    assert page[0] == 0
