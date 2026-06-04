"""AirKorea 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·키 누락 확인.

get_json은 본문 dict를 돌려준다(상류 봉투는 최상위 `{"response": {...}}`). 서비스키는 쿼리
파라미터로 들어가는지(헤더 아님), returnType=json이 붙는지, resultCode 봉투 에러가 매핑되는지
확인한다. 키가 없으면 HTTP 호출 전에 안내를 반환해야 한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.airkorea.tools import register

MOD = "arcsolve.services.airkorea.tools"


def _wrap(header, body=None):
    """상류 봉투 `{"response": {"header":..., "body":...}}`를 만든다."""
    resp = {"header": header}
    if body is not None:
        resp["body"] = body
    return {"response": resp}


@pytest.fixture
def tools(monkeypatch, load_tools):
    """서비스키가 설정된 기본 환경."""
    monkeypatch.setenv("AIRKOREA_SERVICE_KEY", "DECODED_KEY")
    return load_tools(register)


# ─── 시도별 실시간 ──────────────────────────────────────────


async def test_region_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
        {
            "totalCount": 2,
            "pageNo": 1,
            "numOfRows": 100,
            "items": [
                {
                    "dataTime": "2024-01-15 14:00",
                    "stationName": "종로구",
                    "pm10Value": "45",
                    "pm25Value": "21",
                    "o3Value": "0.012",
                    "khaiValue": "67",
                },
                {"dataTime": "2024-01-15 14:00", "stationName": "중구", "pm10Value": "-"},
            ],
        },
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["airkorea_realtime_by_region"](sidoName="서울")
    assert http.last["url"] == (
        "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
    )
    # 서비스키는 쿼리 파라미터(헤더 아님), returnType=json 명시.
    assert http.last["params"]["serviceKey"] == "DECODED_KEY"
    assert http.last["params"]["returnType"] == "json"
    assert http.last["params"]["sidoName"] == "서울"
    assert http.last["params"]["ver"] == "1.3"
    assert http.last.get("headers") is None
    assert "총 2건" in out and "page 1" in out
    assert "종로구" in out and "PM10 45" in out and "PM2.5 21" in out
    assert "PM10 -" in out  # 결측 표시


async def test_region_missing_key_no_network(monkeypatch, load_tools, recording_http):
    monkeypatch.delenv("AIRKOREA_SERVICE_KEY", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_realtime_by_region"](sidoName="서울")
    assert "AIRKOREA_SERVICE_KEY" in out
    assert "Decoding" in out  # 이중 인코딩 함정 안내
    assert not http.calls  # HTTP 전에 막힘


async def test_region_empty_items(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "00"}, {"totalCount": 0, "items": []}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_realtime_by_region"](sidoName="제주")
    assert "데이터 없음" in out


# ─── 측정소별 실시간 ────────────────────────────────────────


async def test_station_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        {
            "totalCount": 1,
            "pageNo": 1,
            "items": [
                {
                    "dataTime": "2024-01-15 14:00",
                    "pm10Value": "30",
                    "pm25Value": "15",
                    "so2Value": "0.003",
                    "khaiValue": "50",
                }
            ],
        },
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["airkorea_realtime_by_station"](stationName="종로구", dataTerm="MONTH")
    assert http.last["url"].endswith("/getMsrstnAcctoRltmMesureDnsty")
    assert http.last["params"]["stationName"] == "종로구"
    assert http.last["params"]["dataTerm"] == "MONTH"
    assert http.last["params"]["returnType"] == "json"
    assert "측정소 종로구" in out
    assert "PM10 30" in out and "PM2.5 15" in out


# ─── 예보 ───────────────────────────────────────────────────


async def test_forecast_request_and_output(tools, monkeypatch, recording_http):
    body = _wrap(
        {"resultCode": "00"},
        {
            "totalCount": 1,
            "pageNo": 1,
            "items": [
                {
                    "dataTime": "2024-01-15 11시 발표",
                    "informCode": "PM10",
                    "informData": "2024-01-15",
                    "informOverall": "전 권역 보통",
                    "informGrade": "서울 : 보통",
                }
            ],
        },
    )
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["airkorea_forecast"](searchDate="2024-01-15", informCode="PM10")
    assert http.last["url"].endswith("/getMinuDustFrcstDspth")
    assert http.last["params"]["searchDate"] == "2024-01-15"
    assert http.last["params"]["informCode"] == "PM10"
    assert "PM10" in out
    assert "전 권역 보통" in out
    assert "서울 : 보통" in out


async def test_forecast_omits_inform_code_when_none(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "00"}, {"totalCount": 0, "items": []}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["airkorea_forecast"](searchDate="2024-01-15")
    assert "informCode" not in http.last["params"]


# ─── resultCode 봉투 에러 매핑(HTTP 200) ───────────────────


async def test_result_code_30_unregistered_key(tools, monkeypatch, recording_http):
    # 등록되지 않은 서비스키 — HTTP 200이지만 봉투 resultCode=30.
    http = recording_http(
        ret=_wrap({"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_realtime_by_region"](sidoName="서울")
    assert "등록되지 않은 서비스키" in out
    assert "Decoding" in out  # 이중 인코딩 힌트


async def test_result_code_22_traffic_limit(tools, monkeypatch, recording_http):
    http = recording_http(
        ret=_wrap({"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_realtime_by_station"](stationName="종로구")
    assert "요청 제한" in out and "500" in out


async def test_result_code_03_no_data(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "03", "resultMsg": "NODATA_ERROR"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_forecast"](searchDate="1999-01-01")
    assert "데이터 없음" in out


async def test_unknown_result_code(tools, monkeypatch, recording_http):
    http = recording_http(ret=_wrap({"resultCode": "77", "resultMsg": "WEIRD"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_realtime_by_region"](sidoName="서울")
    assert "resultCode=77" in out and "WEIRD" in out


# ─── HTTP 4xx/5xx 매핑(게이트웨이 차단 등) ─────────────────


async def test_maps_http_401(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"returnAuthMsg": "SERVICE ACCESS DENIED"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_realtime_by_region"](sidoName="서울")
    assert "401" in out and "SERVICE_KEY" in out


async def test_mapped_http_error_does_not_leak_non_dict_detail(tools, monkeypatch, recording_http):
    # 매핑된 상태(401/403/429)에서는 detail이 dict 메시지만 노출 — 비-JSON 본문은 새지 않는다.
    http = recording_http(exc=UpstreamError(403, "<html><title>403 Forbidden</title></html>"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_realtime_by_region"](sidoName="서울")
    assert "403" in out
    assert "<html>" not in out and "<title>" not in out


async def test_unmapped_http_error_500(tools, monkeypatch, recording_http):
    # 매핑되지 않은 상태(500)는 generic 분기로 떨어진다(payload를 그대로 보여줌 — openalex와 동형).
    http = recording_http(exc=UpstreamError(500, {"resultMsg": "INTERNAL"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["airkorea_forecast"](searchDate="2024-01-15")
    assert "500" in out
