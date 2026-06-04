"""AirKorea 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·쿼리 빌더(serviceKey/returnType=json·페이지네이션·선택 informCode)·
응답 봉투/항목 모델 파싱(문자열 측정값·결측 '-'·extra 무시). HTTP 호출은 일절 하지 않는다.
"""

from arcsolve.services.airkorea.contract import (
    BASE_URL,
    DATA_TERMS,
    DEFAULT_DATA_TERM,
    DEFAULT_NUM_OF_ROWS,
    DEFAULT_PAGE_NO,
    DEFAULT_VER,
    PATH_FORECAST,
    PATH_REALTIME_BY_REGION,
    PATH_REALTIME_BY_STATION,
    RESULT_CODE_OK,
    RETURN_TYPE_JSON,
    SIDO_NAMES,
    ForecastResponse,
    Header,
    RealtimeMeasurement,
    RealtimeResponse,
    build_forecast_params,
    build_realtime_by_region_params,
    build_realtime_by_station_params,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc"
    assert PATH_REALTIME_BY_REGION == "/getCtprvnRltmMesureDnsty"
    assert PATH_REALTIME_BY_STATION == "/getMsrstnAcctoRltmMesureDnsty"
    assert PATH_FORECAST == "/getMinuDustFrcstDspth"
    assert RETURN_TYPE_JSON == "json"
    assert RESULT_CODE_OK == "00"
    assert DEFAULT_NUM_OF_ROWS == 100
    assert DEFAULT_PAGE_NO == 1
    assert DEFAULT_VER == "1.3"
    assert DEFAULT_DATA_TERM == "DAILY"


def test_sido_and_dataterm_enums():
    # 전국 + 17개 광역시·도.
    assert "전국" in SIDO_NAMES
    assert "서울" in SIDO_NAMES and "세종" in SIDO_NAMES
    assert len(SIDO_NAMES) == 18
    assert DATA_TERMS == ("DAILY", "MONTH", "3MONTH")


# ─── 쿼리 빌더 ──────────────────────────────────────────────


def test_build_region_params_includes_key_and_json():
    p = build_realtime_by_region_params(sido_name="서울", service_key="DECODED")
    # 서비스키는 쿼리 파라미터(헤더 아님), returnType=json 명시.
    assert p["serviceKey"] == "DECODED"
    assert p["returnType"] == "json"
    assert p["sidoName"] == "서울"
    assert p["ver"] == "1.3"
    assert p["numOfRows"] == 100
    assert p["pageNo"] == 1


def test_build_region_params_overrides():
    p = build_realtime_by_region_params(
        sido_name="부산", service_key="K", ver="1.4", num_of_rows=10, page_no=2
    )
    assert p["ver"] == "1.4"
    assert p["numOfRows"] == 10
    assert p["pageNo"] == 2


def test_paging_clamped_to_safe_bounds():
    # 공유 clamp_paging 적용: 과도 numOfRows는 상한 9999로, 비정상 pageNo(<1)는 1로 클램프.
    hi = build_realtime_by_region_params(sido_name="서울", service_key="K", num_of_rows=100000)
    assert hi["numOfRows"] == 9999
    lo = build_realtime_by_station_params(station_name="종로구", service_key="K", page_no=0)
    assert lo["pageNo"] == 1
    fc = build_forecast_params(search_date="2024-01-15", service_key="K", num_of_rows=-5)
    assert fc["numOfRows"] == 1


def test_build_station_params():
    p = build_realtime_by_station_params(station_name="종로구", service_key="K")
    assert p["serviceKey"] == "K"
    assert p["returnType"] == "json"
    assert p["stationName"] == "종로구"
    assert p["dataTerm"] == "DAILY"
    assert p["ver"] == "1.3"


def test_build_station_params_dataterm_override():
    p = build_realtime_by_station_params(
        station_name="강남구", service_key="K", data_term="MONTH"
    )
    assert p["dataTerm"] == "MONTH"


def test_build_forecast_params_omits_optional_inform_code():
    p = build_forecast_params(search_date="2024-01-15", service_key="K")
    assert p["serviceKey"] == "K"
    assert p["returnType"] == "json"
    assert p["searchDate"] == "2024-01-15"
    assert "informCode" not in p


def test_build_forecast_params_includes_inform_code():
    p = build_forecast_params(search_date="2024-01-15", service_key="K", inform_code="PM10")
    assert p["informCode"] == "PM10"


# ─── 응답 모델 ──────────────────────────────────────────────


def test_header_model():
    h = Header.model_validate({"resultCode": "00", "resultMsg": "NORMAL_CODE", "x": "ign"})
    assert h.resultCode == "00"
    assert h.resultMsg == "NORMAL_CODE"


def test_measurement_values_are_strings_and_missing_dash():
    # 측정값은 문자열, 결측은 "-" — 캐스팅하지 않는다.
    m = RealtimeMeasurement.model_validate(
        {
            "dataTime": "2024-01-15 14:00",
            "stationName": "종로구",
            "sidoName": "서울",
            "pm10Value": "45",
            "pm25Value": "-",
            "o3Value": "0.012",
            "khaiValue": "67",
            "khaiGrade": "2",
            "unexpected": "ignored",
        }
    )
    assert m.pm10Value == "45"
    assert m.pm25Value == "-"  # 결측은 문자열 그대로
    assert m.khaiValue == "67"
    assert m.stationName == "종로구"


def test_realtime_response_envelope():
    body = {
        "header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
        "body": {
            "totalCount": 40,
            "pageNo": 1,
            "numOfRows": 100,
            "items": [
                {"stationName": "종로구", "pm10Value": "45", "pm25Value": "21"},
                {"stationName": "중구", "pm10Value": "-", "pm25Value": "-"},
            ],
        },
    }
    resp = RealtimeResponse.model_validate(body)
    assert resp.header.resultCode == "00"
    assert resp.body.totalCount == 40
    assert len(resp.body.items) == 2
    assert resp.body.items[1].pm10Value == "-"


def test_realtime_response_error_header():
    # resultCode != "00" (서비스키 오류 등)도 봉투로 받아진다.
    resp = RealtimeResponse.model_validate(
        {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}
    )
    assert resp.header.resultCode == "30"
    assert resp.body is None


def test_forecast_response_envelope():
    body = {
        "header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
        "body": {
            "totalCount": 1,
            "pageNo": 1,
            "numOfRows": 100,
            "items": [
                {
                    "dataTime": "2024-01-15 11시 발표",
                    "informCode": "PM10",
                    "informData": "2024-01-15",
                    "informOverall": "전 권역 보통",
                    "informGrade": "서울 : 보통,부산 : 좋음",
                }
            ],
        },
    }
    resp = ForecastResponse.model_validate(body)
    assert resp.header.resultCode == "00"
    assert resp.body.items[0].informCode == "PM10"
    assert "서울" in resp.body.items[0].informGrade
