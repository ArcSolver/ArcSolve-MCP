"""Seoul Transit 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·키 누락.

get_json은 본문 dict를 돌려준다. 인증키·json·요청위치·역명이 **URL path**에 박히는지(쿼리 아님),
지하철 errorMessage / 따릉이 RESULT 봉투 에러가 매핑되는지, recptnDt가 'N초 전'으로 보정되는지,
1000건 초과가 HTTP 전에 막히는지, 키 2종이 분리(누락 안내)되는지 확인한다.
"""

from datetime import datetime, timedelta

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.seoul_transit.tools import register

MOD = "arcsolve.services.seoul_transit.tools"


@pytest.fixture
def tools(monkeypatch, load_tools):
    """인증키 2종이 모두 설정된 기본 환경."""
    monkeypatch.setenv("SEOUL_SUBWAY_API_KEY", "SUBKEY")
    monkeypatch.setenv("SEOUL_OPENDATA_API_KEY", "OPENKEY")
    return load_tools(register)


# ─── 지하철 실시간 도착 ─────────────────────────────────────


async def test_subway_request_url_and_output(tools, monkeypatch, recording_http):
    body = {
        "errorMessage": {"status": 200, "code": "INFO-000", "message": "정상", "total": 2},
        "realtimeArrivalList": [
            {
                "trainLineNm": "성수행 - 구의방면",
                "arvlMsg2": "전역 출발",
                "arvlMsg3": "교대",
                "btrainSttus": "일반",
                "bstatnNm": "성수",
                "recptnDt": "2024-01-15 14:00:05",
            },
            {"trainLineNm": "외선순환", "arvlMsg2": "3분 후 (역삼)", "bstatnNm": "성수"},
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["seoul_subway_arrivals"](station_name="강남")
    # 인증키·json·서비스·역명이 URL path에 박힌다(쿼리 아님, 헤더 아님).
    assert http.last["url"] == (
        "http://swopenAPI.seoul.go.kr/api/subway/SUBKEY/json/realtimeStationArrival/0/20/강남"
    )
    assert http.last.get("params") is None
    assert http.last.get("headers") is None
    assert "강남역 실시간 도착" in out and "총 2건" in out
    assert "성수행 - 구의방면" in out and "전역 출발" in out
    assert "현재 교대" in out and "성수행" in out  # bstatnNm + 방면


async def test_subway_recptn_dt_age_correction(tools, monkeypatch, recording_http):
    # recptnDt는 과거 시각 — '현재로부터 N초 전 생성' 보정이 붙어야 한다.
    gen = datetime.now() - timedelta(seconds=42)
    body = {
        "errorMessage": {"code": "INFO-000", "total": 1},
        "realtimeArrivalList": [
            {"trainLineNm": "성수행", "arvlMsg2": "전역 출발",
             "recptnDt": gen.strftime("%Y-%m-%d %H:%M:%S")},
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_subway_arrivals"](station_name="강남")
    assert "초 전" in out  # 보정 안내
    # 42초 부근(테스트 실행 지연 흡수 위해 범위로 확인).
    assert any(f"{n}초 전" in out for n in range(41, 46))


async def test_subway_missing_key_no_network(monkeypatch, load_tools, recording_http):
    # 지하철 전용 키 분리: opendata 키만 있어도 지하철은 막힌다.
    monkeypatch.delenv("SEOUL_SUBWAY_API_KEY", raising=False)
    monkeypatch.setenv("SEOUL_OPENDATA_API_KEY", "OPENKEY")
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_subway_arrivals"](station_name="강남")
    assert "SEOUL_SUBWAY_API_KEY" in out
    assert "실시간 지하철 인증키" in out  # 키 분리 안내
    assert not http.calls  # HTTP 전에 막힘


async def test_subway_empty_list(tools, monkeypatch, recording_http):
    http = recording_http(ret={"errorMessage": {"code": "INFO-000"}, "realtimeArrivalList": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_subway_arrivals"](station_name="없는역")
    assert "도착 정보 없음" in out


async def test_subway_auth_error_envelope(tools, monkeypatch, recording_http):
    # 인증키 오류 — HTTP 200이지만 errorMessage.code=INFO-100.
    http = recording_http(
        ret={"errorMessage": {"status": 500, "code": "INFO-100",
                              "message": "인증키가 유효하지 않습니다."}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_subway_arrivals"](station_name="강남")
    assert "인증키 오류" in out and "INFO-100" in out
    assert "SEOUL_SUBWAY_API_KEY" in out


# ─── 따릉이 ─────────────────────────────────────────────────


async def test_bike_request_url_and_output(tools, monkeypatch, recording_http):
    body = {
        "rentBikeStatus": {
            "list_total_count": 2,
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."},
            "row": [
                {"stationName": "102. 망원역 1번출구 앞", "parkingBikeTotCnt": "7",
                 "rackTotCnt": "20", "shared": "35",
                 "stationLatitude": "37.55564", "stationLongitude": "126.91062"},
                {"stationName": "103. 합정역", "parkingBikeTotCnt": "0", "rackTotCnt": "15"},
            ],
        }
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["seoul_bike_status"]()
    # 일반 키·json·요청위치가 URL path에 박힌다.
    assert http.last["url"] == (
        "http://openapi.seoul.go.kr:8088/OPENKEY/json/bikeList/1/1000/"
    )
    assert "망원역" in out and "자전거 7대" in out and "거치대 20" in out
    assert "거치율 35%" in out
    assert "(37.55564, 126.91062)" in out
    assert "전체 2건" in out


async def test_bike_pagination_url(tools, monkeypatch, recording_http):
    http = recording_http(
        ret={"rentBikeStatus": {"list_total_count": 0, "RESULT": {"CODE": "INFO-000"}, "row": []}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["seoul_bike_status"](start=1001, end=2000)
    assert http.last["url"].endswith("/bikeList/1001/2000/")


async def test_bike_over_1000_blocked_before_http(tools, monkeypatch, recording_http):
    # end - start + 1 > 1000 → HTTP 전에 막힌다.
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"](start=1, end=1001)
    assert "최대 1000건" in out
    assert not http.calls


async def test_bike_name_filter(tools, monkeypatch, recording_http):
    body = {
        "rentBikeStatus": {
            "list_total_count": 3,
            "RESULT": {"CODE": "INFO-000"},
            "row": [
                {"stationName": "망원역 1번출구", "parkingBikeTotCnt": "7", "rackTotCnt": "20"},
                {"stationName": "합정역", "parkingBikeTotCnt": "2", "rackTotCnt": "10"},
                {"stationName": "망원2동", "parkingBikeTotCnt": "5", "rackTotCnt": "12"},
            ],
        }
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"](station_name="망원")
    assert "망원역 1번출구" in out and "망원2동" in out
    assert "합정역" not in out
    assert "따릉이 대여소 2건" in out


async def test_bike_filter_no_match(tools, monkeypatch, recording_http):
    body = {
        "rentBikeStatus": {
            "list_total_count": 1,
            "RESULT": {"CODE": "INFO-000"},
            "row": [{"stationName": "합정역", "parkingBikeTotCnt": "2", "rackTotCnt": "10"}],
        }
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"](station_name="없는대여소")
    assert "데이터 없음" in out and "없는대여소" in out


async def test_bike_missing_key_no_network(monkeypatch, load_tools, recording_http):
    # 따릉이 키 분리: subway 키만 있어도 따릉이는 막힌다.
    monkeypatch.setenv("SEOUL_SUBWAY_API_KEY", "SUBKEY")
    monkeypatch.delenv("SEOUL_OPENDATA_API_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"]()
    assert "SEOUL_OPENDATA_API_KEY" in out
    assert not http.calls


async def test_bike_top_level_result_error(tools, monkeypatch, recording_http):
    # 인증키 오류가 서비스 래퍼 없이 최상위 RESULT로 오는 경우.
    http = recording_http(
        ret={"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"]()
    assert "인증키 오류" in out and "INFO-100" in out


async def test_bike_error_336_envelope(tools, monkeypatch, recording_http):
    http = recording_http(
        ret={"rentBikeStatus": {
            "RESULT": {"CODE": "ERROR-336",
                       "MESSAGE": "데이터요청은 한번에 최대 1000건을 넘을 수 없습니다."}}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"]()
    assert "ERROR-336" in out and "1000건" in out


async def test_unknown_code_passthrough(tools, monkeypatch, recording_http):
    http = recording_http(
        ret={"rentBikeStatus": {"RESULT": {"CODE": "ERROR-999", "MESSAGE": "WEIRD"}}}
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"]()
    assert "code=ERROR-999" in out and "WEIRD" in out


# ─── HTTP 4xx/5xx 매핑(게이트웨이 차단 등) ─────────────────


async def test_subway_maps_http_403(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, {"message": "denied"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_subway_arrivals"](station_name="강남")
    assert "403" in out and "SEOUL_SUBWAY_API_KEY" in out


async def test_bike_http_error_does_not_leak_non_dict(tools, monkeypatch, recording_http):
    # 비-JSON(HTML) 본문은 매핑된 상태에서 새지 않는다.
    http = recording_http(exc=UpstreamError(403, "<html><title>403</title></html>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_bike_status"]()
    assert "403" in out
    assert "<html>" not in out and "<title>" not in out


async def test_subway_unmapped_http_500(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(500, {"message": "INTERNAL"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["seoul_subway_arrivals"](station_name="강남")
    assert "500" in out
