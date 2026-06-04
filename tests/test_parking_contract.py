"""Parking(KOTSA 전국 주차정보) 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: base/오퍼레이션 경로 상수·쿼리 빌더(serviceKey/format=2·페이지네이션)·응답 봉투/항목
모델 파싱(문자열 보존·B553881 items quirk 정규화[오퍼레이션명 키 아래 단일/배열/누락]·int 강제
방어). HTTP 호출 없음.
"""

from arcsolve.services.parking.contract import (
    BASE_URL,
    DEFAULT_NUM_OF_ROWS,
    DEFAULT_PAGE_NO,
    FORMAT_JSON,
    FORMAT_XML,
    OP_FACILITY,
    OP_OPERATION,
    OP_REALTIME,
    RESULT_CODE_OK,
    Envelope,
    Facility,
    Operation,
    Realtime,
    build_params,
    normalize_items,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_base_and_operations():
    # 단일 base B553881/Parking + 3개 오퍼레이션.
    assert BASE_URL == "https://apis.data.go.kr/B553881/Parking"
    assert OP_FACILITY == "PrkSttusInfo"
    assert OP_OPERATION == "PrkOprInfo"
    assert OP_REALTIME == "PrkRealtimeInfo"


def test_format_and_defaults():
    # format은 _type/returnType이 아니라 숫자 코드(1=XML, 2=JSON).
    assert FORMAT_JSON == "2"
    assert FORMAT_XML == "1"
    assert RESULT_CODE_OK == "00"
    assert DEFAULT_NUM_OF_ROWS == 100
    assert DEFAULT_PAGE_NO == 1


# ─── 쿼리 빌더 ──────────────────────────────────────────────


def test_build_params_minimal():
    p = build_params(service_key="DECODED")
    assert p["serviceKey"] == "DECODED"
    # format=2(JSON) 명시 — 미지정 시 상류가 XML.
    assert p["format"] == "2"
    assert p["numOfRows"] == 100
    assert p["pageNo"] == 1
    # 개별 주차장 필터(주차장관리번호 등) 입력은 없다.
    assert "prk_center_id" not in p


def test_build_params_pagination_overrides():
    p = build_params(service_key="K", num_of_rows=10, page_no=3)
    assert p["numOfRows"] == 10
    assert p["pageNo"] == 3
    assert p["format"] == "2"


# ─── B553881 items quirk 정규화(오퍼레이션명 키 아래) ───────


def test_normalize_items_array_under_op_key():
    raw = {"PrkSttusInfo": [{"prk_center_id": "A"}, {"prk_center_id": "B"}]}
    out = normalize_items(raw, OP_FACILITY)
    assert len(out) == 2 and out[1]["prk_center_id"] == "B"


def test_normalize_items_single_object_under_op_key():
    # 1건이면 오퍼레이션명 값이 배열이 아닌 단일 객체.
    raw = {"PrkRealtimeInfo": {"prk_center_id": "A", "pkfc_Available_ParkingLots_total": "5"}}
    out = normalize_items(raw, OP_REALTIME)
    assert out == [{"prk_center_id": "A", "pkfc_Available_ParkingLots_total": "5"}]


def test_normalize_items_missing_key():
    # 0건이면 오퍼레이션명 키가 없을 수 있다.
    assert normalize_items({"resultCode": "00", "totalCount": 0}, OP_FACILITY) == []


def test_normalize_items_empty_value():
    assert normalize_items({"PrkOprInfo": ""}, OP_OPERATION) == []
    assert normalize_items({"PrkOprInfo": None}, OP_OPERATION) == []


def test_normalize_items_standard_wrapping_fallback():
    # 게이트웨이가 표준 response.body.items.item으로 줄 경우도 보조 흡수.
    raw = {"body": {"items": {"item": [{"prk_center_id": "X"}]}}}
    out = normalize_items(raw, OP_FACILITY)
    assert out == [{"prk_center_id": "X"}]


def test_normalize_items_non_dict():
    assert normalize_items("", OP_FACILITY) == []
    assert normalize_items(None, OP_FACILITY) == []


# ─── 응답 모델 ──────────────────────────────────────────────


def test_facility_item_preserves_strings():
    f = Facility.model_validate(
        {
            "prk_center_id": "12345-67890-12345-12-1",
            "prk_plce_nm": "서울시 망원동 주차장",
            "prk_plce_adres": "서울시 망원동 월드컵로 1길",
            "prk_plce_entrc_la": 35.879337,  # 숫자로 와도 문자열 보존.
            "prk_plce_entrc_lo": 128.628764,
            "prk_cmprt_co": 100,
            "extra": "ignored",
        }
    )
    assert f.prk_center_id == "12345-67890-12345-12-1"
    assert f.prk_plce_nm == "서울시 망원동 주차장"
    assert f.prk_plce_entrc_la == "35.879337"  # 숫자 → 문자열
    assert f.prk_cmprt_co == "100"


def test_operation_item_fee_and_hours():
    o = Operation.model_validate(
        {
            "prk_center_id": "PK1",
            "opertn_start_time": "080000",
            "opertn_end_time": "200000",
            "opertn_bs_free_time": 30,
            "parking_chrge_bs_time": 30,
            "parking_chrge_bs_chrg": 1500,
            "parking_chrge_adit_unit_time": 30,
            "parking_chrge_adit_unit_chrge": 1000,
        }
    )
    assert o.opertn_start_time == "080000"
    assert o.parking_chrge_bs_chrg == "1500"  # 숫자 → 문자열
    assert o.parking_chrge_adit_unit_chrge == "1000"


def test_realtime_item_available_spaces():
    r = Realtime.model_validate(
        {
            "prk_center_id": "PK1",
            "pkfc_ParkingLots_total": 140,
            "pkfc_Available_ParkingLots_total": 42,  # 현재 잔여면.
        }
    )
    assert r.prk_center_id == "PK1"
    assert r.pkfc_ParkingLots_total == "140"
    assert r.pkfc_Available_ParkingLots_total == "42"


def test_realtime_available_zero_preserved():
    # 잔여 0면도 결측("-")이 아니라 "0"으로 보존돼야 한다.
    r = Realtime.model_validate({"prk_center_id": "PK1", "pkfc_Available_ParkingLots_total": 0})
    assert r.pkfc_Available_ParkingLots_total == "0"


# ─── 봉투 ───────────────────────────────────────────────────


def test_envelope_top_level_result_code_and_int_coercion():
    env = Envelope.model_validate(
        {
            "resultCode": "00",
            "resultMsg": "SUCCESS",
            "totalCount": "100",  # 문자열 숫자.
            "pageNo": 1,
            "numOfRows": "",  # 빈 값 방어.
            "PrkSttusInfo": [{"prk_center_id": "A"}],  # 항목은 봉투 모델이 무시(extra).
        }
    )
    assert env.resultCode == "00"
    assert env.resultMsg == "SUCCESS"
    assert env.totalCount == 100  # 문자열 → int
    assert env.pageNo == 1
    assert env.numOfRows is None


def test_envelope_error_code():
    env = Envelope.model_validate(
        {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}
    )
    assert env.resultCode == "30"
    assert env.totalCount is None
