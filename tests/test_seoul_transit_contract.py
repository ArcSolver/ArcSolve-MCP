"""Seoul Transit 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 호스트·서비스 상수, URL 빌더(인증키·json·요청위치·역명 path 세그먼트),
지하철/따릉이 응답 봉투·항목 모델 파싱(문자열 값·errorMessage/RESULT 봉투·extra 무시).
HTTP 호출은 일절 하지 않는다.
"""

from arcsolve.services.seoul_transit.contract import (
    BIKE_DEFAULT_END,
    BIKE_DEFAULT_START,
    BIKE_MAX_ROWS,
    BIKE_SERVICE,
    OPENDATA_BASE_URL,
    RESULT_CODE_OK,
    SUBWAY_BASE_URL,
    SUBWAY_SERVICE,
    TYPE_JSON,
    BikeResponse,
    BikeStation,
    Result,
    SubwayArrival,
    SubwayErrorMessage,
    SubwayResponse,
    build_bike_url,
    build_subway_url,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    # 지하철: 전용 호스트 swopenAPI.seoul.go.kr/api/subway.
    assert SUBWAY_BASE_URL == "http://swopenAPI.seoul.go.kr/api/subway"
    assert SUBWAY_SERVICE == "realtimeStationArrival"
    # 따릉이: 일반 호스트 openapi.seoul.go.kr:8088.
    assert OPENDATA_BASE_URL == "http://openapi.seoul.go.kr:8088"
    assert BIKE_SERVICE == "bikeList"
    assert TYPE_JSON == "json"
    assert RESULT_CODE_OK == "INFO-000"
    assert BIKE_MAX_ROWS == 1000
    assert BIKE_DEFAULT_START == 1
    assert BIKE_DEFAULT_END == 1000


# ─── URL 빌더 ───────────────────────────────────────────────


def test_build_subway_url_path_segments():
    url = build_subway_url(station_name="강남", api_key="SUBKEY")
    # 인증키·json·서비스·요청위치·역명이 path 세그먼트로 박힌다(쿼리 아님).
    assert url == (
        "http://swopenAPI.seoul.go.kr/api/subway/SUBKEY/json/realtimeStationArrival/0/20/강남"
    )
    assert "?" not in url  # 쿼리스트링 아님


def test_build_subway_url_overrides():
    url = build_subway_url(station_name="서울", api_key="K", start=0, end=5)
    assert url.endswith("/realtimeStationArrival/0/5/서울")


def test_build_bike_url_path_and_trailing_slash():
    url = build_bike_url(api_key="OPENKEY")
    assert url == "http://openapi.seoul.go.kr:8088/OPENKEY/json/bikeList/1/1000/"
    # 끝 슬래시 포함(공식 예시 형식).
    assert url.endswith("/")


def test_build_bike_url_pagination():
    url = build_bike_url(api_key="K", start=1001, end=2000)
    assert url.endswith("/bikeList/1001/2000/")


# ─── 지하철 응답 모델 ──────────────────────────────────────


def test_subway_error_message_normal_envelope():
    # 정상 응답에도 errorMessage가 존재하며 code=INFO-000.
    em = SubwayErrorMessage.model_validate(
        {
            "status": 200,
            "code": "INFO-000",
            "message": "정상 처리되었습니다.",
            "total": 4,
            "link": "ignored",
        }
    )
    assert em.code == "INFO-000"
    assert em.total == 4


def test_subway_arrival_values_are_strings():
    a = SubwayArrival.model_validate(
        {
            "subwayId": "1002",
            "updnLine": "상행",
            "trainLineNm": "성수행 - 구의방면",
            "statnNm": "강남",
            "arvlMsg2": "전역 출발",
            "arvlMsg3": "교대",
            "arvlCd": "3",
            "btrainSttus": "일반",
            "bstatnNm": "성수",
            "recptnDt": "2024-01-15 14:00:05",
            "barvlDt": "0",
            "ordkey": "01000성수0",
            "unexpected": "ignored",
        }
    )
    assert a.subwayId == "1002"
    assert a.arvlMsg2 == "전역 출발"
    assert a.arvlCd == "3"
    assert a.bstatnNm == "성수"
    assert a.recptnDt == "2024-01-15 14:00:05"


def test_subway_response_envelope():
    body = {
        "errorMessage": {"status": 200, "code": "INFO-000", "message": "정상", "total": 2},
        "realtimeArrivalList": [
            {"trainLineNm": "성수행", "arvlMsg2": "전역 출발", "bstatnNm": "성수"},
            {"trainLineNm": "외선순환", "arvlMsg2": "3분 후 (역삼)", "bstatnNm": "성수"},
        ],
    }
    resp = SubwayResponse.model_validate(body)
    assert resp.errorMessage.code == "INFO-000"
    assert resp.errorMessage.total == 2
    assert len(resp.realtimeArrivalList) == 2
    assert resp.realtimeArrivalList[0].arvlMsg2 == "전역 출발"


def test_subway_response_error_envelope():
    # 인증키 오류 — errorMessage.code != INFO-000, list 비거나 없음.
    resp = SubwayResponse.model_validate(
        {"errorMessage": {"status": 500, "code": "INFO-100", "message": "인증키가 유효하지 않습니다."}}
    )
    assert resp.errorMessage.code == "INFO-100"
    assert resp.realtimeArrivalList == []


# ─── 따릉이 응답 모델 ──────────────────────────────────────


def test_bike_station_values_are_strings():
    r = BikeStation.model_validate(
        {
            "rackTotCnt": "20",
            "stationName": "102. 망원역 1번출구 앞",
            "parkingBikeTotCnt": "7",
            "shared": "35",
            "stationLatitude": "37.55564",
            "stationLongitude": "126.91062",
            "stationId": "ST-4",
            "unexpected": "ignored",
        }
    )
    assert r.parkingBikeTotCnt == "7"
    assert r.shared == "35"
    assert r.stationName == "102. 망원역 1번출구 앞"
    assert r.stationLatitude == "37.55564"


def test_bike_response_normal_envelope():
    body = {
        "rentBikeStatus": {
            "list_total_count": 2,
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."},
            "row": [
                {"stationName": "망원역", "parkingBikeTotCnt": "7", "rackTotCnt": "20"},
                {"stationName": "합정역", "parkingBikeTotCnt": "0", "rackTotCnt": "15"},
            ],
        }
    }
    resp = BikeResponse.model_validate(body)
    assert resp.rentBikeStatus.RESULT.CODE == "INFO-000"
    assert resp.rentBikeStatus.list_total_count == 2
    assert len(resp.rentBikeStatus.row) == 2
    assert resp.rentBikeStatus.row[1].parkingBikeTotCnt == "0"


def test_bike_response_top_level_result_error():
    # 인증키/요청 오류는 서비스 래퍼 없이 최상위 RESULT로 올 수 있다.
    resp = BikeResponse.model_validate(
        {"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}
    )
    assert resp.rentBikeStatus is None
    assert resp.RESULT.CODE == "INFO-100"


def test_result_model():
    r = Result.model_validate({"CODE": "ERROR-336", "MESSAGE": "최대 1000건", "x": "ign"})
    assert r.CODE == "ERROR-336"
    assert r.MESSAGE == "최대 1000건"
