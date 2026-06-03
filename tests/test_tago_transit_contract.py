"""TAGO Transit 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 서비스/오퍼레이션 경로 상수·쿼리 빌더(serviceKey/_type=json·페이지네이션·코드 의존
파라미터)·응답 봉투/항목 모델 파싱(문자열 보존·items quirk 정규화·int 강제 방어). HTTP 호출 없음.
"""

from arcsolve.services.tago_transit.contract import (
    BASE_URL,
    DEFAULT_NUM_OF_ROWS,
    DEFAULT_PAGE_NO,
    OP_BUS_ARRIVAL,
    OP_CITY_CODE,
    OP_EXP_BUS,
    OP_ROUTE_STATIONS,
    OP_STATION_SEARCH,
    OP_SUBURBS_BUS,
    OP_TRAIN,
    RESULT_CODE_OK,
    SERVICE_BUS_ARRIVAL,
    SERVICE_BUS_ROUTE,
    SERVICE_BUS_STATION,
    SERVICE_EXP_BUS,
    SERVICE_SUBURBS_BUS,
    SERVICE_TRAIN,
    TYPE_JSON,
    BusArrival,
    Body,
    CityCode,
    Header,
    Response,
    Train,
    build_bus_arrival_params,
    build_city_code_params,
    build_route_stations_params,
    build_station_search_params,
    build_terminal_bus_params,
    build_train_params,
    normalize_items,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_base_and_namespace():
    # 전국 대중교통 통합 네임스페이스 1613000.
    assert BASE_URL == "http://apis.data.go.kr/1613000"
    assert TYPE_JSON == "json"
    assert RESULT_CODE_OK == "00"
    assert DEFAULT_NUM_OF_ROWS == 100
    assert DEFAULT_PAGE_NO == 1


def test_service_paths_match_official():
    assert SERVICE_BUS_ARRIVAL == "/ArvlInfoInqireService"
    assert SERVICE_BUS_STATION == "/BusSttnInfoInqireService"
    assert SERVICE_BUS_ROUTE == "/BusRouteInfoInqireService"
    assert SERVICE_EXP_BUS == "/ExpBusInfoService"
    assert SERVICE_SUBURBS_BUS == "/SuburbsBusInfoService"
    assert SERVICE_TRAIN == "/TrainInfoService"


def test_operation_paths_match_official():
    assert OP_BUS_ARRIVAL == "/getSttnAcctoArvlPrearngeInfoList"
    assert OP_CITY_CODE == "/getCtyCodeList"
    assert OP_STATION_SEARCH == "/getSttnNoList"
    assert OP_ROUTE_STATIONS == "/getRouteAcctoThrghSttnList"
    assert OP_EXP_BUS == "/getStrtpntAlocFndExpbusInfo"
    assert OP_SUBURBS_BUS == "/getStrtpntAlocFndSuberbsBusInfo"
    assert OP_TRAIN == "/getCtyAcctoTrainList"


# ─── 쿼리 빌더 ──────────────────────────────────────────────


def test_city_code_params_minimal():
    p = build_city_code_params(service_key="DECODED")
    assert p["serviceKey"] == "DECODED"
    assert p["_type"] == "json"
    # cityCode/nodeId 같은 추가 입력은 없다.
    assert "cityCode" not in p


def test_station_search_params():
    p = build_station_search_params(city_code="25", node_name="시청", service_key="K")
    assert p["serviceKey"] == "K"
    assert p["_type"] == "json"
    assert p["cityCode"] == "25"
    assert p["nodeNm"] == "시청"
    assert p["numOfRows"] == 100
    assert p["pageNo"] == 1


def test_bus_arrival_params_code_dependency():
    # 코드 의존: cityCode + nodeId 필수.
    p = build_bus_arrival_params(city_code="25", node_id="DJB8001793", service_key="K")
    assert p["cityCode"] == "25"
    assert p["nodeId"] == "DJB8001793"
    assert p["_type"] == "json"


def test_route_stations_params():
    p = build_route_stations_params(city_code="25", route_id="DJB30300004", service_key="K")
    assert p["cityCode"] == "25"
    assert p["routeId"] == "DJB30300004"
    assert p["_type"] == "json"


def test_terminal_bus_params_shared_by_exp_and_intercity():
    p = build_terminal_bus_params(
        dep_terminal_id="NAEK010", arr_terminal_id="NAEK300",
        dep_date="20240115", service_key="K",
    )
    assert p["depTerminalId"] == "NAEK010"
    assert p["arrTerminalId"] == "NAEK300"
    assert p["depPlandTime"] == "20240115"
    assert p["_type"] == "json"


def test_train_params_use_place_ids():
    p = build_train_params(
        dep_station_id="NAT010000", arr_station_id="NAT013271",
        dep_date="20240115", service_key="K",
    )
    assert p["depPlaceId"] == "NAT010000"
    assert p["arrPlaceId"] == "NAT013271"
    assert p["depPlandTime"] == "20240115"
    assert p["_type"] == "json"


def test_pagination_overrides():
    p = build_bus_arrival_params(
        city_code="25", node_id="X", service_key="K", num_of_rows=10, page_no=3
    )
    assert p["numOfRows"] == 10
    assert p["pageNo"] == 3


# ─── items quirk 정규화 ─────────────────────────────────────


def test_normalize_items_empty_string():
    # 0건이면 items가 빈 문자열 "".
    assert normalize_items("") == []
    assert normalize_items(None) == []


def test_normalize_items_single_object():
    # 1건이면 item이 배열이 아닌 단일 객체.
    out = normalize_items({"item": {"nodeid": "A", "routeno": "100"}})
    assert out == [{"nodeid": "A", "routeno": "100"}]


def test_normalize_items_array():
    out = normalize_items({"item": [{"nodeid": "A"}, {"nodeid": "B"}]})
    assert len(out) == 2 and out[1]["nodeid"] == "B"


def test_normalize_items_item_empty_string():
    # items는 dict이나 item이 빈 문자열인 경우도 흡수.
    assert normalize_items({"item": ""}) == []


def test_normalize_items_direct_list():
    out = normalize_items([{"nodeid": "A"}])
    assert out == [{"nodeid": "A"}]


# ─── 응답 모델 ──────────────────────────────────────────────


def test_header_model():
    h = Header.model_validate({"resultCode": "00", "resultMsg": "NORMAL SERVICE.", "x": "ign"})
    assert h.resultCode == "00"
    assert h.resultMsg == "NORMAL SERVICE."


def test_body_item_dicts_and_int_coercion():
    b = Body.model_validate(
        {
            "items": {"item": [{"nodeid": "A"}, {"nodeid": "B"}]},
            "totalCount": "2",  # 상류가 문자열 숫자로 줄 수 있다.
            "pageNo": 1,
            "numOfRows": "",  # 빈 값은 None으로 방어.
        }
    )
    assert b.totalCount == 2  # 문자열 → int
    assert b.pageNo == 1
    assert b.numOfRows is None
    assert len(b.item_dicts()) == 2


def test_bus_arrival_item_preserves_strings():
    a = BusArrival.model_validate(
        {
            "nodeid": "DJB8001793",
            "nodenm": "시청",
            "routeno": 100,  # 숫자로 와도 문자열로 보존.
            "routetp": "간선버스",
            "arrprevstationcnt": 3,
            "vehicletp": "일반차량",
            "arrtime": 180,
            "extra": "ignored",
        }
    )
    assert a.routeno == "100"
    assert a.arrprevstationcnt == "3"
    assert a.arrtime == "180"
    assert a.nodenm == "시청"


def test_city_code_item():
    cc = CityCode.model_validate({"citycode": 25, "cityname": "대전"})
    assert cc.citycode == "25"  # 숫자 → 문자열
    assert cc.cityname == "대전"


def test_train_item_lowercase_fields():
    t = Train.model_validate(
        {
            "traingradename": "KTX",
            "trainno": 101,
            "depplandtime": "20240115060000",
            "arrplandtime": "20240115080000",
            "depplacename": "서울",
            "arrplacename": "부산",
            "adultcharge": 59800,
        }
    )
    assert t.traingradename == "KTX"
    assert t.trainno == "101"
    assert t.adultcharge == "59800"


def test_response_envelope_full():
    body = {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {
            "items": {"item": [{"nodeid": "A", "routeno": "100", "arrtime": "120"}]},
            "totalCount": 1,
            "pageNo": 1,
            "numOfRows": 100,
        },
    }
    resp = Response.model_validate(body)
    assert resp.header.resultCode == "00"
    assert resp.body.totalCount == 1
    assert resp.body.item_dicts()[0]["routeno"] == "100"


def test_response_error_header_no_body():
    resp = Response.model_validate(
        {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}
    )
    assert resp.header.resultCode == "30"
    assert resp.body is None


def test_response_empty_items_string():
    # 무데이터: body.items가 빈 문자열.
    resp = Response.model_validate(
        {"header": {"resultCode": "00"}, "body": {"items": "", "totalCount": 0}}
    )
    assert resp.body.item_dicts() == []
