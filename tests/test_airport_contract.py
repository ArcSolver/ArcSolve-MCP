"""Airport(인천공항 운항현황) 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 기관코드/서비스/오퍼레이션 경로 상수·쿼리 빌더(serviceKey/`type=json`·시간범위·
선택 필터·페이지네이션)·응답 봉투/항목 모델 파싱(문자열 보존·items quirk 정규화·int 강제 방어).
HTTP 호출 없음.
"""

from arcsolve.services.airport.contract import (
    BASE_URL,
    DEFAULT_FROM_TIME,
    DEFAULT_NUM_OF_ROWS,
    DEFAULT_PAGE_NO,
    DEFAULT_TO_TIME,
    LANG_KOREAN,
    OP_ARRIVALS,
    OP_DEPARTURES,
    RESULT_CODE_OK,
    SERVICE_PASSENGER_FLIGHTS,
    TERMINAL_NAMES,
    TYPE_JSON,
    Body,
    Header,
    PassengerFlight,
    Response,
    build_flight_params,
    normalize_items,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_base_and_institution_code():
    # 인천국제공항공사 기관코드 B551177.
    assert BASE_URL == "https://apis.data.go.kr/B551177"
    assert SERVICE_PASSENGER_FLIGHTS == "/StatusOfPassengerFlightsDeOdp"
    assert TYPE_JSON == "json"
    assert RESULT_CODE_OK == "00"
    assert DEFAULT_NUM_OF_ROWS == 100
    assert DEFAULT_PAGE_NO == 1
    assert DEFAULT_FROM_TIME == "0000"
    assert DEFAULT_TO_TIME == "2400"
    assert LANG_KOREAN == "K"


def test_operation_paths_match_official():
    assert OP_ARRIVALS == "/getPassengerArrivalsDeOdp"
    assert OP_DEPARTURES == "/getPassengerDeparturesDeOdp"


def test_terminal_names_map_codes():
    # 상류는 표시명이 아니라 코드(P01/P02/P03)를 준다.
    assert TERMINAL_NAMES["P01"] == "T1"
    assert TERMINAL_NAMES["P02"] == "탑승동"
    assert TERMINAL_NAMES["P03"] == "T2"


# ─── 쿼리 빌더 ──────────────────────────────────────────────


def test_flight_params_minimal_uses_type_not_underscore_type():
    # ⚠️ 인천공항은 `_type`이 아니라 `type` 파라미터.
    p = build_flight_params(service_key="DECODED")
    assert p["serviceKey"] == "DECODED"
    assert p["type"] == "json"
    assert "_type" not in p
    # 시간범위·언어·페이지네이션 기본값.
    assert p["from_time"] == "0000"
    assert p["to_time"] == "2400"
    assert p["lang"] == "K"
    assert p["numOfRows"] == 100
    assert p["pageNo"] == 1
    # search_day 미지정 시 보내지 않는다(상류 기본=당일).
    assert "searchday" not in p
    # 선택 필터는 None이면 빠진다.
    assert "airport_code" not in p
    assert "flight_id" not in p


def test_flight_params_full():
    p = build_flight_params(
        service_key="K",
        search_day="20240115",
        from_time="0600",
        to_time="1200",
        airport_code="NRT",
        flight_id="KE001",
        lang="E",
        num_of_rows=50,
        page_no=2,
    )
    assert p["searchday"] == "20240115"
    assert p["from_time"] == "0600"
    assert p["to_time"] == "1200"
    assert p["airport_code"] == "NRT"
    assert p["flight_id"] == "KE001"
    assert p["lang"] == "E"
    assert p["numOfRows"] == 50
    assert p["pageNo"] == 2


# ─── items quirk 정규화 ─────────────────────────────────────


def test_normalize_items_empty():
    assert normalize_items("") == []
    assert normalize_items(None) == []
    assert normalize_items([]) == []


def test_normalize_items_direct_list():
    # 인천공항 기본형: items가 곧장 리스트.
    out = normalize_items([{"flightId": "KE001"}, {"flightId": "OZ102"}])
    assert len(out) == 2 and out[1]["flightId"] == "OZ102"


def test_normalize_items_single_object():
    # 1건이면 items가 곧장 단일 객체.
    out = normalize_items({"flightId": "KE001", "airline": "대한항공"})
    assert out == [{"flightId": "KE001", "airline": "대한항공"}]


def test_normalize_items_item_nesting_other_service_form():
    # 타 data.go.kr 서비스형(item 중첩)도 흡수.
    assert normalize_items({"item": [{"flightId": "A"}]}) == [{"flightId": "A"}]
    assert normalize_items({"item": {"flightId": "B"}}) == [{"flightId": "B"}]
    assert normalize_items({"item": ""}) == []


# ─── 응답 모델 ──────────────────────────────────────────────


def test_header_model():
    h = Header.model_validate({"resultCode": "00", "resultMsg": "NORMAL SERVICE.", "x": "ign"})
    assert h.resultCode == "00"
    assert h.resultMsg == "NORMAL SERVICE."


def test_body_int_coercion_and_item_dicts():
    b = Body.model_validate(
        {
            "items": [{"flightId": "KE001"}, {"flightId": "OZ102"}],
            "totalCount": "2",  # 상류가 문자열 숫자로 줄 수 있다.
            "pageNo": 1,
            "numOfRows": "",  # 빈 값은 None으로 방어.
        }
    )
    assert b.totalCount == 2
    assert b.pageNo == 1
    assert b.numOfRows is None
    assert len(b.item_dicts()) == 2


def test_passenger_flight_arrival_fields_preserve_strings():
    f = PassengerFlight.model_validate(
        {
            "airline": "대한항공",
            "flightId": "KE001",
            "airport": "나리타",
            "airportCode": "NRT",
            "scheduleDateTime": "202401151230",
            "estimatedDateTime": "202401151245",
            "terminalid": 2,  # 숫자로 와도 문자열 보존.
            "carousel": 7,
            "exitnumber": "A",
            "remark": "도착",
            "fid": 12345,
            "extra": "ignored",
        }
    )
    assert f.terminalid == "2"
    assert f.carousel == "7"
    assert f.fid == "12345"
    assert f.airline == "대한항공"
    assert f.scheduleDateTime == "202401151230"


def test_passenger_flight_departure_fields():
    f = PassengerFlight.model_validate(
        {
            "airline": "아시아나",
            "flightId": "OZ102",
            "airportCode": "LAX",
            "chkinrange": "A~C",
            "gatenumber": 24,
            "remark": "탑승중",
            "terminalid": "P03",
        }
    )
    assert f.chkinrange == "A~C"
    assert f.gatenumber == "24"
    assert f.remark == "탑승중"
    assert f.terminalid == "P03"  # 코드 원문 보존(표시 환산은 tools에서)


def test_passenger_flight_codeshare_fields():
    # 공동운항 필드(codeshare/masterflightid) — 다수 외부 구현으로 확정.
    f = PassengerFlight.model_validate(
        {"flightId": "DL7861", "codeshare": "Slave", "masterflightid": "KE081"}
    )
    assert f.codeshare == "Slave"
    assert f.masterflightid == "KE081"


def test_response_envelope_full_direct_list_items():
    body = {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {
            "items": [{"flightId": "KE001", "airline": "대한항공", "carousel": "7"}],
            "totalCount": 1,
            "pageNo": 1,
            "numOfRows": 100,
        },
    }
    resp = Response.model_validate(body)
    assert resp.header.resultCode == "00"
    assert resp.body.totalCount == 1
    assert resp.body.item_dicts()[0]["flightId"] == "KE001"


def test_response_error_header_no_body():
    resp = Response.model_validate(
        {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}
    )
    assert resp.header.resultCode == "30"
    assert resp.body is None


def test_response_empty_items():
    resp = Response.model_validate(
        {"header": {"resultCode": "00"}, "body": {"items": "", "totalCount": 0}}
    )
    assert resp.body.item_dicts() == []
