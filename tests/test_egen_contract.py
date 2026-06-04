"""E-Gen 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·쿼리 빌더(serviceKey Decoding 원문·STAGE1 필수·STAGE2 생략·페이지네이션)·
XML 봉투/항목 파싱(문자열 값·결측·MKioskTy 수집·게이트웨이 cmmMsgHeader 에러). HTTP 없음.
"""

from arcsolve.services.egen.contract import (
    BASE_URL,
    DEFAULT_NUM_OF_ROWS,
    DEFAULT_PAGE_NO,
    PATH_LIST,
    PATH_REALTIME_BEDS,
    PATH_SEVERE_ACCEPTANCE,
    RESULT_CODE_OK,
    Header,
    Institution,
    RealtimeBeds,
    build_list_params,
    build_realtime_beds_params,
    build_severe_acceptance_params,
    parse_header,
    parse_list,
    parse_realtime_beds,
    parse_severe_acceptance,
)

import xml.etree.ElementTree as ET


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://apis.data.go.kr/B552657/ErmctInfoInqireService"
    assert PATH_REALTIME_BEDS == "/getEmrrmRltmUsefulSckbdInfoInqire"
    assert PATH_SEVERE_ACCEPTANCE == "/getSrsillDissAceptncPosblInfoInqire"
    assert PATH_LIST == "/getEgytListInfoInqire"
    assert RESULT_CODE_OK == "00"
    assert DEFAULT_NUM_OF_ROWS == 100
    assert DEFAULT_PAGE_NO == 1


# ─── 쿼리 빌더 ──────────────────────────────────────────────


def test_build_realtime_includes_key_and_stage1():
    p = build_realtime_beds_params(stage1="서울특별시", service_key="DECODED")
    # 서비스키는 쿼리 파라미터(헤더 아님) — Decoding 키 원문(httpx 자동 인코딩에 맡김).
    assert p["serviceKey"] == "DECODED"
    assert p["STAGE1"] == "서울특별시"
    assert p["numOfRows"] == 100
    assert p["pageNo"] == 1
    # STAGE2 미지정이면 키 자체가 빠진다(시도 전체).
    assert "STAGE2" not in p


def test_build_realtime_includes_stage2_when_given():
    p = build_realtime_beds_params(
        stage1="경기도", service_key="K", stage2="성남시 분당구", num_of_rows=10, page_no=2
    )
    assert p["STAGE2"] == "성남시 분당구"
    assert p["numOfRows"] == 10
    assert p["pageNo"] == 2


def test_build_severe_and_list_share_shape():
    sev = build_severe_acceptance_params(stage1="부산광역시", service_key="K")
    lst = build_list_params(stage1="부산광역시", service_key="K", stage2="해운대구")
    assert sev["STAGE1"] == "부산광역시" and "STAGE2" not in sev
    assert lst["STAGE2"] == "해운대구"
    assert sev["serviceKey"] == "K" and lst["serviceKey"] == "K"


def test_empty_stage2_is_omitted():
    # 빈 문자열 STAGE2도 생략(falsy) — 시도 전체로 동작.
    p = build_list_params(stage1="대구광역시", service_key="K", stage2="")
    assert "STAGE2" not in p


# ─── 응답 모델 / XML 파싱 ──────────────────────────────────

REALTIME_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item>
        <hpid>A1100001</hpid>
        <dutyName>서울대학교병원</dutyName>
        <dutyTel3>02-2072-0000</dutyTel3>
        <hvidate>20240115140000</hvidate>
        <hvec>12</hvec>
        <hvoc>3</hvoc>
        <hvicc>5</hvicc>
        <hvgc>40</hvgc>
        <hvctayn>Y</hvctayn>
        <hvmriayn>Y</hvmriayn>
        <hvventiayn>N</hvventiayn>
        <hvamyn>Y</hvamyn>
      </item>
      <item>
        <hpid>A1100002</hpid>
        <dutyName>중구보건소</dutyName>
        <hvec>-</hvec>
        <hvctayn>N</hvctayn>
      </item>
    </items>
    <numOfRows>100</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>2</totalCount>
  </body>
</response>"""

SEVERE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item>
        <hpid>A1100001</hpid>
        <dutyName>서울대학교병원</dutyName>
        <hvidate>20240115140000</hvidate>
        <MKioskTy1>Y</MKioskTy1>
        <MKioskTy2>N</MKioskTy2>
        <MKioskTy8>Y</MKioskTy8>
      </item>
    </items>
    <numOfRows>100</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>1</totalCount>
  </body>
</response>"""

LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item>
        <rnum>1</rnum>
        <hpid>A1100001</hpid>
        <dutyName>서울대학교병원</dutyName>
        <dutyAddr>서울특별시 종로구 대학로 101</dutyAddr>
        <dutyTel1>02-2072-2114</dutyTel1>
        <dutyTel3>02-2072-0000</dutyTel3>
        <dutyEmclsName>권역응급의료센터</dutyEmclsName>
        <wgs84Lon>126.999</wgs84Lon>
        <wgs84Lat>37.579</wgs84Lat>
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


def test_realtime_bed_values_are_strings_and_missing_dash():
    # 가용수/가용여부는 문자열, 결측 '-'/'N'은 캐스팅하지 않는다.
    m = RealtimeBeds.model_validate(
        {"hpid": "A1", "dutyName": "X병원", "hvec": "12", "hvctayn": "Y", "unexpected": "ign"}
    )
    assert m.hvec == "12"
    assert m.hvctayn == "Y"
    assert m.dutyName == "X병원"


def test_institution_model_geo_strings():
    inst = Institution.model_validate(
        {"hpid": "A1", "dutyName": "X", "wgs84Lat": "37.5", "wgs84Lon": "127.0"}
    )
    assert inst.wgs84Lat == "37.5"
    assert inst.wgs84Lon == "127.0"


def test_parse_realtime_beds_envelope_and_page():
    header, items, page = parse_realtime_beds(REALTIME_XML)
    assert header.resultCode == "00"
    assert page == (2, 1, 100)  # totalCount, pageNo, numOfRows
    assert len(items) == 2
    assert items[0].dutyName == "서울대학교병원"
    assert items[0].hvec == "12"
    assert items[0].hvctayn == "Y"
    assert items[1].hvec == "-"  # 결측은 문자열 그대로


def test_parse_severe_collects_mkiosk_slots():
    header, items, page = parse_severe_acceptance(SEVERE_XML)
    assert header.resultCode == "00"
    assert page == (1, 1, 100)
    assert len(items) == 1
    it = items[0]
    assert it.dutyName == "서울대학교병원"
    # MKioskTy* 슬롯은 고정 모델이 아니라 mkiosk dict(라벨=값)로 수집된다.
    assert it.mkiosk == {"MKioskTy1": "Y", "MKioskTy2": "N", "MKioskTy8": "Y"}


def test_parse_list_fields():
    header, items, page = parse_list(LIST_XML)
    assert header.resultCode == "00"
    assert len(items) == 1
    h = items[0]
    assert h.dutyName == "서울대학교병원"
    assert h.dutyAddr == "서울특별시 종로구 대학로 101"
    assert h.dutyTel3 == "02-2072-0000"
    assert h.dutyEmclsName == "권역응급의료센터"
    assert h.wgs84Lat == "37.579" and h.wgs84Lon == "126.999"


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
    header, items, page = parse_realtime_beds(xml)
    assert header.resultCode == "03"
    assert items == []
    assert page[0] == 0
